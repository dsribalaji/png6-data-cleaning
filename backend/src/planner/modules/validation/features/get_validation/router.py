"""Router for get_validation feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.modules.validation.features.get_validation.service import get_validation
from planner.modules.validation.schemas import ValidationResponse

router = APIRouter(prefix="/api/v1/plans", tags=["validation"])


def _any_user() -> None:
    """placeholder for require_roles(...) until the users module lands (W1)"""


@router.get("/{plan_id}/validation", response_model=ValidationResponse)
async def get_plan_validation(
    plan_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(_any_user),
) -> ValidationResponse:
    """Get latest validation results for a plan."""
    return await get_validation(session, plan_id)
