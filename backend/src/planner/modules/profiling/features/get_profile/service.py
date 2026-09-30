"""Service implementation for get_profile feature."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.modules.profiling.errors import ProfilingErrors
from planner.modules.profiling.models import ColumnProfileRow, ProfileRun
from planner.modules.profiling.schemas import ColumnProfileOut, ProfileResponse


async def get_profile(session: AsyncSession, dataset_id: UUID) -> ProfileResponse:
    """Load dataset profile run and column profiles, returning ProfileResponse."""
    stmt_run = select(ProfileRun).where(ProfileRun.dataset_id == dataset_id)
    result_run = await session.execute(stmt_run)
    run = result_run.scalar_one_or_none()
    if run is None:
        raise ProfilingErrors.PROFILE_NOT_FOUND

    stmt_cols = (
        select(ColumnProfileRow)
        .where(ColumnProfileRow.dataset_id == dataset_id)
        .order_by(ColumnProfileRow.ordinal.asc())
    )
    result_cols = await session.execute(stmt_cols)
    col_rows = result_cols.scalars().all()

    # Record audit defensively
    try:
        await record_audit(
            session=session,
            event_type="dataset.profile_viewed",
            object_type="dataset",
            object_id=str(dataset_id),
            details={"column_count": run.column_count},
        )
    except (NotImplementedError, Exception):
        # Audit sink not implemented yet
        pass

    columns = [
        ColumnProfileOut(
            name=col.column_name,
            ordinal=col.ordinal,
            physical_type=col.physical_type,
            semantic_type=col.semantic_type,
            null_count=col.null_count,
            null_pct=col.null_pct,
            distinct_count=col.distinct_count,
            min_value=col.min_value,
            max_value=col.max_value,
            mean_value=col.mean_value,
            flags=col.flags or [],
        )
        for col in col_rows
    ]

    return ProfileResponse(
        dataset_id=run.dataset_id,
        row_count=run.row_count,
        column_count=run.column_count,
        columns=columns,
        issues=run.issues or [],
        profiled_at=run.profiled_at,
    )
