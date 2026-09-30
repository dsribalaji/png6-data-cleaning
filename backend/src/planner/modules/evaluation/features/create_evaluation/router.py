"""FastAPI router for creating evaluation runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
# Auth: require_roles is a security dependency owned by worker W1 (comment noting dependency)
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.evaluation.features.create_evaluation.schemas import (
    CreateEvaluationIn,
    CreateEvaluationOut,
)
from planner.modules.evaluation.features.create_evaluation.service import create_evaluation

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=CreateEvaluationOut)
async def create_evaluation_endpoint(
    payload: CreateEvaluationIn | None = None,
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(require_roles("data_engineer", "administrator")),
) -> CreateEvaluationOut:
    """Create an evaluation run for a benchmark set (roles: data_engineer, administrator)."""
    return await create_evaluation(
        session,
        payload,
        actor_id=principal.user_id,
        actor_role=principal.role,
    )
