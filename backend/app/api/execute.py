"""Plan execution and rollback API router.

STATUS: scaffold stub — not implemented.
"""

import uuid
from fastapi import APIRouter, HTTPException, Response, status

from app.schemas.execution import ExecutionResultOut, RollbackRequest, RollbackResultOut

router = APIRouter(prefix="/execute", tags=["execute"])


@router.post("/{plan_id}", response_model=ExecutionResultOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def execute_plan(plan_id: uuid.UUID) -> ExecutionResultOut:
    """Execute an approved cleaning plan deterministically on a copy (FR-035).

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")


@router.post("/{plan_id}/rollback", response_model=RollbackResultOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def rollback_plan(plan_id: uuid.UUID, req: RollbackRequest) -> RollbackResultOut:
    """Roll back execution to a specific version byte-for-byte (FR-033, FR-034).

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")


# FR-043: Export withheld when any test run fails
@router.get("/{plan_id}/export", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def export_dataset(plan_id: uuid.UUID) -> Response:
    """Export cleaned dataset. Export is strictly withheld if any test fails (FR-043).

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")
