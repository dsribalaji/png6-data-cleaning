"""Service implementation for create_plan feature."""

from __future__ import annotations

from typing import Any
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.modules.planning.models import LossEstimateRow, Plan, PlanStep
from planner.modules.planning.schemas import (
    CreatePlanRequest,
    LossEstimateOut,
    PlanOut,
    PlanStepOut,
)


async def create_plan(
    session: AsyncSession,
    dataset_id: UUID,
    req: CreatePlanRequest,
    actor_id: UUID | None = None,
) -> PlanOut:
    """Create a new cleaning plan for a dataset and enqueue planner.generate_plan."""
    plan = Plan(
        dataset_id=dataset_id,
        status="proposed",
        loss_threshold=req.loss_threshold if req.loss_threshold is not None else 0.05,
    )
    session.add(plan)
    await session.flush()

    job_id = uuid.uuid4()

    # Commit BEFORE dispatching (integration 2026-09-30): in eager/demo mode
    # the task runs inline in a separate thread with its own DB session, so
    # the plan must be visible to it.
    await session.commit()

    # Enqueue task (eager-aware: runs inline in demo mode, publishes in prod).
    # send_task_eager_aware handles the running event loop internally.
    try:
        from planner.worker import send_task_eager_aware

        send_task_eager_aware(
            "planner.generate_plan",
            args=[str(dataset_id), str(job_id), str(plan.id)],
            queue="plan",
        )
    except Exception:
        # In testing or standalone worker configurations, dispatch may fail
        pass

    # Audit defensively
    try:
        await record_audit(
            session=session,
            event_type="plan.created",
            object_type="plan",
            object_id=str(plan.id),
            user_id=actor_id,
            details={"dataset_id": str(dataset_id), "loss_threshold": plan.loss_threshold},
        )
    except (NotImplementedError, Exception):
        pass

    await session.commit()
    await session.refresh(plan)

    # In eager mode, the task might have populated steps inline, so query them
    stmt_steps = (
        select(PlanStep)
        .where(PlanStep.plan_id == plan.id)
        .order_by(PlanStep.step_no.asc())
    )
    res_steps = await session.execute(stmt_steps)
    step_rows = res_steps.scalars().all()

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
                source=step.source or "deterministic",
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
        ai_status=plan.ai_status,
        ai_message=plan.ai_message,
    )
