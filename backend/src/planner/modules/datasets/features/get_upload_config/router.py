"""Router for upload configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from planner.core.security import RequestPrincipal, get_current_principal
from planner.modules.datasets.features.get_upload_config.schemas import UploadConfigResponse
from planner.modules.datasets.features.get_upload_config.service import get_upload_config_service

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("/upload", response_model=UploadConfigResponse)
async def get_upload_config(
    principal: RequestPrincipal = Depends(get_current_principal),
) -> UploadConfigResponse:
    """Get upload configuration limits and supported file extensions."""
    return await get_upload_config_service(principal=principal)
