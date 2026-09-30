"""Router for get_profile feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.modules.profiling.features.get_profile.schemas import ProfileResponse
from planner.modules.profiling.features.get_profile.service import get_profile


async def _any_user() -> None:
    """Placeholder for require_roles(...) until the users module lands (W1)."""
    return None


router = APIRouter(prefix="/api/v1/datasets/{dataset_id}", tags=["profiling"])


@router.get("/profile", response_model=ProfileResponse)
async def get_dataset_profile_endpoint(
    dataset_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(_any_user),
) -> ProfileResponse:
    """Retrieve column-level and dataset-level profile metrics."""
    return await get_profile(session, dataset_id)
