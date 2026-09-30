"""Service for listing datasets with pagination."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.pagination import Page, build_page
from planner.core.security import RequestPrincipal
from planner.modules.datasets.features.upload_dataset.schemas import DatasetRead
from planner.modules.datasets.models import Dataset


async def list_datasets_service(
    page: int,
    page_size: int,
    session: AsyncSession,
    principal: RequestPrincipal,
) -> Page[DatasetRead]:
    """Retrieve paginated list of datasets ordered by creation time descending."""
    count_stmt = select(func.count()).select_from(Dataset)
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(Dataset)
        .order_by(Dataset.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    datasets = result.scalars().all()

    items = [DatasetRead.model_validate(d) for d in datasets]
    return build_page(items=items, total=total, page=page, page_size=page_size)
