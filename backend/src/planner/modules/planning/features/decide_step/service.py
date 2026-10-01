"""Service implementation for decide_step feature."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.core.errors import AppError
from planner.engine.ops.base import OPS
from planner.modules.planning.errors import PlanningErrors
from planner.modules.planning.models import LossEstimateRow, Plan, PlanStep
from planner.modules.planning.schemas import DecideStepRequest, LossEstimateOut, PlanStepOut
from planner.modules.profiling.models import ColumnProfileRow

ALLOWED_DECISIONS = {"accepted", "edited", "rejected"}


async def decide_step(
    session: AsyncSession,
    plan_id: UUID,
    step_id: UUID,
    req: DecideStepRequest,
    actor_id: UUID | None = None,
) -> PlanStepOut:
    """Record an engineer decision on a specific plan step."""
    stmt_plan = select(Plan).where(Plan.id == plan_id)
    res_plan = await session.execute(stmt_plan)
    plan = res_plan.scalar_one_or_none()
    if plan is None:
        raise PlanningErrors.PLAN_NOT_FOUND

    if plan.status != "proposed":
        raise PlanningErrors.PLAN_NOT_DECIDABLE

    stmt_step = select(PlanStep).where(PlanStep.id == step_id, PlanStep.plan_id == plan_id)
    res_step = await session.execute(stmt_step)
    step = res_step.scalar_one_or_none()
    if step is None:
        raise PlanningErrors.STEP_NOT_FOUND

    if req.decision not in ALLOWED_DECISIONS:
        raise PlanningErrors.INVALID_DECISION

    if req.decision == "edited" and req.parameters is not None:
        # Load dataset schema or build schema hint
        stmt_cols = select(ColumnProfileRow).where(ColumnProfileRow.dataset_id == plan.dataset_id)
        res_cols = await session.execute(stmt_cols)
        col_rows = res_cols.scalars().all()
        if col_rows:
            schema_hint = {c.column_name: c.physical_type for c in col_rows}
        else:
            col_name = req.parameters.get("column") or req.parameters.get("name")
            schema_hint = {col_name: "String"} if col_name else {}

        if step.operation not in OPS:
            raise AppError("INVALID_PARAMETERS", f"Unknown operation: {step.operation}", 400)

        try:
            OPS[step.operation].validate(req.parameters, schema_hint)
        except ValueError as exc:
            raise AppError("INVALID_PARAMETERS", str(exc), 400) from exc

        step.parameters = req.parameters

        # Attempt loss re-estimation if snapshot frame is accessible
        try:
            from planner.engine.loss.estimator import estimate_step_loss
            from planner.modules.execution.public import read_snapshot_frame

            df = await read_snapshot_frame(plan_id, 0)
            new_loss = estimate_step_loss(df, step.operation, step.parameters)
            stmt_loss = select(LossEstimateRow).where(LossEstimateRow.step_id == step.id)
            res_loss = await session.execute(stmt_loss)
            loss_row = res_loss.scalar_one_or_none()
            if loss_row is not None:
                loss_row.rows_affected = new_loss.rows_affected
                loss_row.columns_affected = new_loss.columns_affected
                loss_row.cells_affected = new_loss.cells_affected
                loss_row.estimated_loss = new_loss.estimated_loss
        except Exception:
            # Snapshot frame not available or execution.public not landed; retain previous estimate
            pass

    step.decision = req.decision
    step.decision_reason = req.reason
    step.decided_at = datetime.now(timezone.utc)
    step.decided_by = actor_id

    # Defensive audit
    try:
        await record_audit(
            session=session,
            event_type="plan.step_decided",
            object_type="plan_step",
            object_id=str(step.id),
            user_id=actor_id,
            details={
                "plan_id": str(plan_id),
                "step_no": step.step_no,
                "decision": req.decision,
                "reason": req.reason,
            },
        )
    except (NotImplementedError, Exception):
        pass

    await session.commit()
    await session.refresh(step)

    stmt_loss = select(LossEstimateRow).where(LossEstimateRow.step_id == step.id)
    res_loss = await session.execute(stmt_loss)
    loss_row = res_loss.scalar_one_or_none()
    loss_out = (
        LossEstimateOut(
            rows_affected=loss_row.rows_affected,
            columns_affected=loss_row.columns_affected,
            cells_affected=loss_row.cells_affected,
            estimated_loss=float(loss_row.estimated_loss),
        )
        if loss_row is not None
        else None
    )

    return PlanStepOut(
        id=step.id,
        step_no=step.step_no,
        operation=step.operation,
        parameters=step.parameters,
        rationale=step.rationale,
        confidence=float(step.confidence),
        decision=step.decision,
        decision_reason=step.decision_reason,
        estimated_loss=loss_out,
        source=step.source or "deterministic",
    )
