"""Datasets API router.

STATUS: scaffold stub — validation logic is real; storage and ingest pipeline not started.
"""

from pathlib import Path
import uuid
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.dataset import DatasetListOut, DatasetOut, UploadResponse

router = APIRouter(prefix="/datasets", tags=["datasets"])

ALLOWED_EXTENSIONS = {".xlsx", ".csv"}


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def upload_dataset(file: UploadFile = File(...)) -> UploadResponse:
    """Upload a dataset file (FR-001).

    Validation logic is real:
    - Verifies extension in {.xlsx, .csv} (400 if invalid)
    - Verifies size <= settings.upload_max_mb (PROPOSED 50 MB, 413 if exceeded)
    Storage and background ingest are not started (returns 501).
    """
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    # PROPOSED: 50 MB upload limit (contract §6, P3)
    if size_mb > settings.upload_max_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed upload size of {settings.upload_max_mb} MB",
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="ingest pipeline not started",
    )


@router.get("", response_model=DatasetListOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def list_datasets() -> DatasetListOut:
    """List all datasets.

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")


@router.get("/{dataset_id}", response_model=DatasetOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_dataset(dataset_id: uuid.UUID) -> DatasetOut:
    """Retrieve metadata for a specific dataset.

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")
