"""Router for retrieving quarantine records of a dataset."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.pagination import Page, page_params
from planner.core.security import RequestPrincipal, get_current_principal
from planner.modules.datasets.features.get_quarantine.schemas import QuarantineRecordRead
from planner.modules.datasets.features.get_quarantine.service import get_quarantine_service

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.get("/{id}/quarantine", response_model=Page[QuarantineRecordRead])
async def get_quarantine(
    id: UUID,
    page_and_size: tuple[int, int] = Depends(page_params),
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> Page[QuarantineRecordRead]:
    """Get paginated quarantine records for a dataset."""
    page, page_size = page_and_size
    return await get_quarantine_service(
        dataset_id=id,
        page=page,
        page_size=page_size,
        session=session,
        principal=principal,
    )
