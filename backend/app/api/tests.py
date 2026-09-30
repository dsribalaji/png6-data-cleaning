"""Verification tests API router.

STATUS: scaffold stub — not implemented.
"""

from typing import Literal
import uuid
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.tests import TestCaseOut, TestRunOut

# FR-039 to FR-041: Unit and integration tests generated and run before and after execution
router = APIRouter(prefix="/tests", tags=["tests"])


@router.get("/{plan_id}", response_model=list[TestCaseOut], status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_tests(plan_id: uuid.UUID) -> list[TestCaseOut]:
    """Retrieve generated test cases for a cleaning plan (FR-039, FR-040).

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")


@router.post("/{plan_id}/run", response_model=TestRunOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def run_tests(
    plan_id: uuid.UUID,
    phase: Literal["pre", "post"] = Query("post", description="Execution phase (pre or post execution)"),
) -> TestRunOut:
    """Execute generated verification test suite (FR-041).

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")
