"""Router for get_rules feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.modules.profiling.features.get_rules.schemas import RulesResponse
from planner.modules.profiling.features.get_rules.service import get_rules


async def _any_user() -> None:
    """Placeholder for require_roles(...) until the users module lands (W1)."""
    return None


router = APIRouter(prefix="/api/v1/datasets/{dataset_id}", tags=["profiling"])


@router.get("/rules", response_model=RulesResponse)
async def get_dataset_rules_endpoint(
    dataset_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(_any_user),
) -> RulesResponse:
    """Retrieve inferred cleaning rules for a dataset."""
    return await get_rules(session, dataset_id)
