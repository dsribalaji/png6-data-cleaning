"""Router for listing datasets."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.pagination import Page, page_params
from planner.core.security import RequestPrincipal, get_current_principal
from planner.modules.datasets.features.list_datasets.service import list_datasets_service
from planner.modules.datasets.features.upload_dataset.schemas import DatasetRead

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.get("", response_model=Page[DatasetRead])
async def list_datasets(
    page_and_size: tuple[int, int] = Depends(page_params),
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> Page[DatasetRead]:
    """List datasets with pagination."""
    page, page_size = page_and_size
    return await list_datasets_service(
        page=page,
        page_size=page_size,
        session=session,
        principal=principal,
    )
