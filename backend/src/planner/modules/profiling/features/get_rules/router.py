"""Router for get_rules feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.profiling.features.get_rules.schemas import RulesResponse
from planner.modules.profiling.features.get_rules.service import get_rules

router = APIRouter(prefix="/api/v1/datasets/{dataset_id}", tags=["profiling"])


@router.get("/rules", response_model=RulesResponse)
async def get_dataset_rules_endpoint(
    dataset_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: RequestPrincipal = Depends(
        require_roles("data_engineer", "administrator", "auditor", "viewer")
    ),
) -> RulesResponse:
    """Retrieve inferred cleaning rules for a dataset."""
    return await get_rules(session, dataset_id)
