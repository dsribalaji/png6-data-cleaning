"""Router for get_plan feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.modules.planning.features.get_plan.schemas import PlanOut
from planner.modules.planning.features.get_plan.service import get_plan


async def _any_user() -> None:
    """Placeholder for require_roles(...) until the users module lands (W1)."""
    return None


router = APIRouter(prefix="/api/v1/plans", tags=["planning"])


@router.get("/{plan_id}", response_model=PlanOut)
async def get_plan_endpoint(
    plan_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(_any_user),
) -> PlanOut:
    """Retrieve a cleaning plan by its ID."""
    return await get_plan(session, plan_id)
