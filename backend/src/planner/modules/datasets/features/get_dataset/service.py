"""Service for getting a dataset by ID."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.security import RequestPrincipal
from planner.modules.datasets.features.upload_dataset.schemas import DatasetRead
from planner.modules.datasets.helpers import get_dataset_or_404


async def get_dataset_service(
    dataset_id: UUID,
    session: AsyncSession,
    principal: RequestPrincipal,
) -> DatasetRead:
    """Retrieve a single dataset by ID, raising 404 NOT_FOUND if absent."""
    dataset = await get_dataset_or_404(session=session, dataset_id=dataset_id)
    return DatasetRead.model_validate(dataset)
