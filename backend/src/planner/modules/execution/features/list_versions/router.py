"""Router for list_versions feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.modules.execution.features.list_versions.service import list_versions
from planner.modules.execution.schemas import VersionsResponse

router = APIRouter(prefix="/api/v1/plans", tags=["execution"])


def _any_user() -> None:
    """placeholder for require_roles(...) until the users module lands (W1)"""


@router.get("/{plan_id}/versions", response_model=VersionsResponse)
async def get_plan_versions(
    plan_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(_any_user),
) -> VersionsResponse:
    """Get list of executed versions for a plan."""
    return await list_versions(session, plan_id)
