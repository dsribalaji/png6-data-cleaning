"""Router for decide_step feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.planning.features.decide_step.schemas import DecideStepRequest, PlanStepOut
from planner.modules.planning.features.decide_step.service import decide_step

router = APIRouter(prefix="/api/v1/plans", tags=["planning"])


@router.patch("/{plan_id}/steps/{step_id}", response_model=PlanStepOut)
async def decide_step_endpoint(
    plan_id: UUID,
    step_id: UUID,
    req: DecideStepRequest,
    session: AsyncSession = Depends(get_session),
    _auth: RequestPrincipal = Depends(require_roles("data_engineer", "administrator")),
) -> PlanStepOut:
    """Accept, edit, or reject a proposed plan step."""
    return await decide_step(session, plan_id, step_id, req)
