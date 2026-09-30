"""Service implementation for get_plan feature."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.modules.planning.errors import PlanningErrors
from planner.modules.planning.models import LossEstimateRow, Plan, PlanStep
from planner.modules.planning.schemas import LossEstimateOut, PlanOut, PlanStepOut


async def get_plan(session: AsyncSession, plan_id: UUID) -> PlanOut:
    """Retrieve full cleaning plan with ordered steps and loss estimates."""
    stmt_plan = select(Plan).where(Plan.id == plan_id)
    res_plan = await session.execute(stmt_plan)
    plan = res_plan.scalar_one_or_none()
    if plan is None:
        raise PlanningErrors.PLAN_NOT_FOUND

    stmt_steps = (
        select(PlanStep)
        .where(PlanStep.plan_id == plan_id)
        .order_by(PlanStep.step_no.asc())
    )
    res_steps = await session.execute(stmt_steps)
    step_rows = res_steps.scalars().all()

    # Audit defensively
    try:
        await record_audit(
            session=session,
            event_type="plan.viewed",
            object_type="plan",
            object_id=str(plan_id),
            details={"step_count": len(step_rows)},
        )
    except (NotImplementedError, Exception):
        pass

    steps_out: list[PlanStepOut] = []
    for step in step_rows:
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
        steps_out.append(
            PlanStepOut(
                id=step.id,
                step_no=step.step_no,
                operation=step.operation,
                parameters=step.parameters,
                rationale=step.rationale,
                confidence=float(step.confidence),
                decision=step.decision,
                decision_reason=step.decision_reason,
                estimated_loss=loss_out,
            )
        )

    return PlanOut(
        id=plan.id,
        dataset_id=plan.dataset_id,
        status=plan.status,
        total_estimated_loss=float(plan.total_estimated_loss),
        loss_threshold=float(plan.loss_threshold),
        steps=steps_out,
        created_at=plan.created_at,
    )
