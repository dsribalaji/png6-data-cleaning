"""FastAPI router for listing evaluation runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.pagination import Page
# Auth: require_roles is a security dependency owned by worker W1 (comment noting dependency)
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.evaluation.features.list_evaluations.schemas import (
    EvaluationRunOut,
    ListEvaluationsIn,
)
from planner.modules.evaluation.features.list_evaluations.service import list_evaluations

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.get("", response_model=Page[EvaluationRunOut])
async def list_evaluations_endpoint(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=200, alias="pageSize", description="Items per page"),
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(
        require_roles("data_engineer", "administrator", "auditor", "viewer")
    ),
) -> Page[EvaluationRunOut]:
    """List evaluation runs with pagination.
    Roles: data_engineer, administrator, auditor, viewer.
    """
    input_data = ListEvaluationsIn(page=page, page_size=page_size)
    return await list_evaluations(
        session,
        input_data,
        actor_id=principal.user_id,
        actor_role=principal.role,
    )


__all__ = ["router"]
