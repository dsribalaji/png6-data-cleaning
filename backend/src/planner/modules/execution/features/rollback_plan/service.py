"""Service for requesting a plan rollback."""

from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.execution.errors import ExecutionErrors
from planner.modules.execution.models import PipelineVersion, RollbackRow
from planner.modules.execution.schemas import RollbackRequest, RollbackResponse


async def rollback_request(
    session: AsyncSession,
    plan_id: UUID,
    req: RollbackRequest,
    actor_id: UUID | None = None,
) -> RollbackResponse:
    """Validate rollback parameters, enqueue task, and record rollback request."""
    reason = req.reason.strip()
    if len(reason) < 10:
        raise ExecutionErrors.REASON_REQUIRED

    stmt = (
        select(PipelineVersion)
        .where(PipelineVersion.plan_id == plan_id)
        .order_by(PipelineVersion.version_no.asc())
    )
    result = await session.execute(stmt)
    versions = list(result.scalars().all())
    if not versions:
        raise ExecutionErrors.PLAN_NOT_FOUND

    target = next((v for v in versions if v.version_no == req.to_version), None)
    if target is None:
        raise ExecutionErrors.VERSION_NOT_FOUND

    from_version = max(v.version_no for v in versions)
    job_id = uuid.uuid4()

    # Persist the request before dispatching: in eager mode the task runs inline
    # and must find this row to mark it completed.
    rollback_row = RollbackRow(
        id=uuid.uuid4(),
        plan_id=plan_id,
        from_version_no=from_version,
        to_version_no=req.to_version,
        reason=reason,
        requested_by=actor_id,
        completed_at=None,
    )
    session.add(rollback_row)
    await session.commit()

    from planner.core.audit import record_audit

    await record_audit(
        session,
        user_id=actor_id,
        event_type="rollback.requested",
        object_type="plan",
        object_id=str(plan_id),
        details={"to_version": req.to_version, "from_version": from_version, "reason": reason},
    )

    from planner.worker import send_task_eager_aware

    send_task_eager_aware(
        "planner.rollback_plan",
        args=[str(plan_id), str(job_id), req.to_version, reason],
        queue="execute",
    )

    return RollbackResponse(
        plan_id=plan_id,
        from_version=from_version,
        to_version=req.to_version,
        job_id=job_id,
    )
