"""Service for retrieving upload configuration."""

from __future__ import annotations

from planner.core.config import settings
from planner.core.security import RequestPrincipal
from planner.modules.datasets.features.get_upload_config.schemas import UploadConfigResponse


async def get_upload_config_service(
    principal: RequestPrincipal,
) -> UploadConfigResponse:
    """Return upload constraints and default loss threshold for the UI."""
    return UploadConfigResponse(
        max_file_mb=settings.upload_max_mb,
        allowed_extensions=[".xlsx", ".csv"],
        loss_threshold_default=settings.loss_threshold_default,
    )
