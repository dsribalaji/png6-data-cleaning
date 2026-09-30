"""Router for approve_plan feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.modules.planning.features.approve_plan.schemas import ApproveResponse
from planner.modules.planning.features.approve_plan.service import approve_plan


async def _engineer_only() -> None:
    """Placeholder for require_roles(...) until the users module lands (W1)."""
    return None


router = APIRouter(prefix="/api/v1/plans", tags=["planning"])


@router.post(
    "/{plan_id}/approve",
    response_model=ApproveResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def approve_plan_endpoint(
    plan_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(_engineer_only),
) -> ApproveResponse:
    """Approve a fully decided cleaning plan and launch test generation/execution."""
    return await approve_plan(session, plan_id)
