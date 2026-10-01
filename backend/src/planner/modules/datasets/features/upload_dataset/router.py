"""Upload dataset router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.config import settings
from planner.core.db import get_session
from planner.core.ratelimit import rate_limit
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.datasets.features.upload_dataset.schemas import DatasetRead
from planner.modules.datasets.features.upload_dataset.service import upload_dataset_service

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.post(
    "",
    response_model=DatasetRead,
    status_code=201,
    dependencies=[Depends(rate_limit("upload", lambda: settings.rate_limit_upload_per_minute))],
)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(None, min_length=3, max_length=80, pattern=r"^[A-Za-z0-9 _.\-]+$"),
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(
        require_roles("data_engineer", "administrator")
    ),
) -> DatasetRead:
    """Upload a new .xlsx or .csv dataset, validate headers, and enqueue ingestion."""
    return await upload_dataset_service(
        file=file,
        session=session,
        principal=principal,
        name=name,
    )
