"""Profiling API router.

STATUS: scaffold stub — not implemented.
"""

import uuid
from fastapi import APIRouter, HTTPException, status

from app.schemas.profile import ProfileReportOut

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("/{dataset_id}/run", response_model=ProfileReportOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def run_profile(dataset_id: uuid.UUID) -> ProfileReportOut:
    """Trigger profiling over an entire dataset (FR-006 to FR-012, BR-08).

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")


@router.get("/{dataset_id}", response_model=ProfileReportOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_profile(dataset_id: uuid.UUID) -> ProfileReportOut:
    """Get the profiling report for a dataset.

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")
