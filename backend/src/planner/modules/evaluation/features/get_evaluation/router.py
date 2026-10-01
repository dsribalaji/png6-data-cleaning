"""FastAPI router for retrieving evaluation run detail."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session

# Auth: require_roles is a security dependency owned by worker W1 (comment noting dependency)
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.evaluation.features.get_evaluation.schemas import (
    EvaluationRunOut,
    GetEvaluationIn,
)
from planner.modules.evaluation.features.get_evaluation.service import get_evaluation

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.get("/{run_id}", response_model=EvaluationRunOut)
async def get_evaluation_endpoint(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(
        require_roles("data_engineer", "administrator", "auditor", "viewer")
    ),
) -> EvaluationRunOut:
    """Get evaluation run details by ID (roles: data_engineer, administrator, auditor, viewer)."""
    input_data = GetEvaluationIn(run_id=run_id)
    return await get_evaluation(
        session,
        input_data,
        actor_id=principal.user_id,
        actor_role=principal.role,
    )


__all__ = ["router"]
