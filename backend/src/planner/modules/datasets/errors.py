"""Static AppError instances for the datasets module (Backend.md)."""

from __future__ import annotations

from planner.core.config import settings
from planner.core.errors import AppError, app_error


class DatasetsErrors:
    """Static and formatted AppError instances for dataset operations."""

    DATASET_NAME_TAKEN = app_error("DATASET_NAME_TAKEN")
    UNSUPPORTED_FILE_TYPE = app_error("UNSUPPORTED_FILE_TYPE")
    FILE_TOO_LARGE = app_error("FILE_TOO_LARGE", limit=settings.upload_max_mb)
    NOT_FOUND = app_error("NOT_FOUND")

    @staticmethod
    def file_too_large(limit: float) -> AppError:
        """Return a formatted FILE_TOO_LARGE error for a specific size limit."""
        return app_error("FILE_TOO_LARGE", limit=limit)
