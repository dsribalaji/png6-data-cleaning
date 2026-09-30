"""Router for decide_step feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.modules.planning.features.decide_step.schemas import DecideStepRequest, PlanStepOut
from planner.modules.planning.features.decide_step.service import decide_step


async def _engineer_only() -> None:
    """Placeholder for require_roles(...) until the users module lands (W1)."""
    return None


router = APIRouter(prefix="/api/v1/plans", tags=["planning"])


@router.patch("/{plan_id}/steps/{step_id}", response_model=PlanStepOut)
async def decide_step_endpoint(
    plan_id: UUID,
    step_id: UUID,
    req: DecideStepRequest,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(_engineer_only),
) -> PlanStepOut:
    """Accept, edit, or reject a proposed plan step."""
    return await decide_step(session, plan_id, step_id, req)
