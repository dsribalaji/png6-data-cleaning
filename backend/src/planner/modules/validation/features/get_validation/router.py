"""Router for get_validation feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.validation.features.get_validation.service import get_validation
from planner.modules.validation.schemas import ValidationResponse

router = APIRouter(prefix="/api/v1/plans", tags=["validation"])


@router.get("/{plan_id}/validation", response_model=ValidationResponse)
async def get_plan_validation(
    plan_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: RequestPrincipal = Depends(
        require_roles("data_engineer", "administrator", "auditor", "viewer")
    ),
) -> ValidationResponse:
    """Get latest validation results for a plan."""
    return await get_validation(session, plan_id)
