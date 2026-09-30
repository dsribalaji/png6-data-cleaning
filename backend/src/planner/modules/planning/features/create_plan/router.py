"""Router for create_plan feature."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.planning.features.create_plan.schemas import CreatePlanRequest, PlanOut
from planner.modules.planning.features.create_plan.service import create_plan

router = APIRouter(prefix="/api/v1/datasets/{dataset_id}", tags=["planning"])


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_dataset_plan_endpoint(
    dataset_id: UUID,
    req: CreatePlanRequest = CreatePlanRequest(),
    session: AsyncSession = Depends(get_session),
    _auth: RequestPrincipal = Depends(require_roles("data_engineer", "administrator")),
) -> PlanOut:
    """Generate a cleaning plan for an ingested dataset."""
    return await create_plan(session, dataset_id, req)
