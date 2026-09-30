"""Service for listing quarantine records for a dataset."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.pagination import Page, build_page
from planner.core.security import RequestPrincipal
from planner.modules.datasets.features.get_quarantine.schemas import QuarantineRecordRead
from planner.modules.datasets.models import QuarantineRecord
from planner.modules.datasets.helpers import get_dataset_or_404


async def get_quarantine_service(
    dataset_id: UUID,
    page: int,
    page_size: int,
    session: AsyncSession,
    principal: RequestPrincipal,
) -> Page[QuarantineRecordRead]:
    """Retrieve paginated quarantine records for a dataset, ensuring dataset exists."""
    # Ensure dataset exists; raises 404 NOT_FOUND if absent
    await get_dataset_or_404(session=session, dataset_id=dataset_id)

    count_stmt = (
        select(func.count())
        .select_from(QuarantineRecord)
        .where(QuarantineRecord.dataset_id == dataset_id)
    )
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(QuarantineRecord)
        .where(QuarantineRecord.dataset_id == dataset_id)
        .order_by(QuarantineRecord.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    items = [QuarantineRecordRead.model_validate(r) for r in records]
    return build_page(items=items, total=total, page=page, page_size=page_size)
