"""Service for listing pipeline versions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.execution.errors import ExecutionErrors
from planner.modules.execution.models import PipelineVersion
from planner.modules.execution.schemas import VersionOut, VersionsResponse


async def list_versions(session: AsyncSession, plan_id: UUID) -> VersionsResponse:
    """List all pipeline versions for a plan, ordered by version_no."""
    try:
        from planner.modules.planning.public import get_plan_row
    except (ImportError, AttributeError) as exc:
        raise RuntimeError("planning.public not implemented") from exc

    plan = await get_plan_row(session, plan_id)
    if plan is None:
        raise ExecutionErrors.PLAN_NOT_FOUND

    stmt = (
        select(PipelineVersion)
        .where(PipelineVersion.plan_id == plan_id)
        .order_by(PipelineVersion.version_no.asc())
    )
    result = await session.execute(stmt)
    versions = list(result.scalars().all())

    max_version = max((v.version_no for v in versions), default=-1)

    items = [
        VersionOut(
            version_no=v.version_no,
            step_id=v.step_id,
            created_at=v.created_at,
            executed_by=v.executed_by,
            is_current=(v.version_no == max_version),
        )
        for v in versions
    ]
    return VersionsResponse(plan_id=plan_id, items=items, total=len(items))
