"""Cleaning plans API router.

STATUS: scaffold stub — not implemented.
"""

import uuid
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.schemas.plan import ApprovalIn, PlanOut

router = APIRouter(prefix="/plans", tags=["plans"])


class GeneratePlanIn(BaseModel):
    """Payload to request plan generation."""

    dataset_id: uuid.UUID = Field(..., description="Target dataset identifier")


@router.post("/generate", response_model=PlanOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def generate_plan(payload: GeneratePlanIn) -> PlanOut:
    """Generate a deterministic cleaning plan from dataset profile (FR-021, FR-022).

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")


@router.get("/{plan_id}", response_model=PlanOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_plan(plan_id: uuid.UUID) -> PlanOut:
    """Retrieve an existing cleaning plan with steps and loss estimates.

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")


# FR-027: User approval workflow supporting accept / edit / reject decisions per step
@router.post("/{plan_id}/approve", response_model=PlanOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def approve_plan(plan_id: uuid.UUID, approval: ApprovalIn) -> PlanOut:
    """Submit approval decisions (accept/edit/reject) for plan steps (FR-027).

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")
