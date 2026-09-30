"""Service implementation for approve_plan feature."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.core.events import EventType, PlanApprovedPayload
from planner.core.outbox import add_event
from planner.modules.planning.errors import PlanningErrors
from planner.modules.planning.models import Plan, PlanStep
from planner.modules.planning.schemas import ApproveResponse


async def approve_plan(
    session: AsyncSession,
    plan_id: UUID,
    actor_id: UUID | None = None,
) -> ApproveResponse:
    """Approve a proposed plan where all steps have been decided, enqueuing validation."""
    stmt_plan = select(Plan).where(Plan.id == plan_id)
    res_plan = await session.execute(stmt_plan)
    plan = res_plan.scalar_one_or_none()
    if plan is None:
        raise PlanningErrors.PLAN_NOT_FOUND

    if plan.status != "proposed":
        raise PlanningErrors.PLAN_NOT_DECIDABLE

    stmt_steps = select(PlanStep).where(PlanStep.plan_id == plan_id)
    res_steps = await session.execute(stmt_steps)
    steps = res_steps.scalars().all()

    if any(step.decision == "pending" for step in steps):
        raise PlanningErrors.PLAN_NOT_FULLY_DECIDED

    job_id = uuid.uuid4()
    plan.status = "approved"
    plan.approved_by = actor_id
    plan.approved_at = datetime.now(timezone.utc)

    # Outbox event
    await add_event(session, EventType.PLAN_APPROVED, PlanApprovedPayload(plan_id=plan.id))

    # Commit BEFORE dispatching (integration 2026-09-30): eager task runs in
    # a separate thread/session and must see the approved status.
    await session.commit()

    # Enqueue validation test generation (eager-aware).
    try:
        from planner.worker import send_task_eager_aware

        send_task_eager_aware(
            "planner.generate_tests",
            args=[str(plan.id), str(job_id)],
            queue="validate",
        )
    except Exception:
        pass

    # Audit defensively
    try:
        await record_audit(
            session=session,
            event_type="plan.approved",
            object_type="plan",
            object_id=str(plan.id),
            user_id=actor_id,
            details={"job_id": str(job_id), "steps_count": len(steps)},
        )
    except (NotImplementedError, Exception):
        pass

    await session.commit()
    await session.refresh(plan)

    return ApproveResponse(
        plan_id=plan.id,
        status=plan.status,
        job_id=job_id,
    )
