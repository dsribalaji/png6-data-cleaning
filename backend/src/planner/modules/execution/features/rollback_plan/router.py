"""Router for rollback_plan feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.modules.execution.features.rollback_plan.service import rollback_request
from planner.modules.execution.schemas import RollbackRequest, RollbackResponse

router = APIRouter(prefix="/api/v1/plans", tags=["execution"])


def _engineer_only() -> None:
    """placeholder for require_roles(...) until the users module lands (W1)"""


@router.post(
    "/{plan_id}/rollback",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RollbackResponse,
)
async def rollback_plan_endpoint(
    plan_id: UUID,
    req: RollbackRequest,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(_engineer_only),
) -> RollbackResponse:
    """Request a plan rollback to a previous version."""
    return await rollback_request(session, plan_id, req, actor_id=None)
