"""Router for getting a dataset by ID."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, get_current_principal
from planner.modules.datasets.features.get_dataset.service import get_dataset_service
from planner.modules.datasets.features.upload_dataset.schemas import DatasetRead

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.get("/{id}", response_model=DatasetRead)
async def get_dataset(
    id: UUID,
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> DatasetRead:
    """Get dataset details by ID."""
    return await get_dataset_service(
        dataset_id=id,
        session=session,
        principal=principal,
    )
