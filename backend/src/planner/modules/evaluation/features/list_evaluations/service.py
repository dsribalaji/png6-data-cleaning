"""Service for listing evaluation runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.pagination import Page, build_page
from planner.modules.evaluation.features.list_evaluations.schemas import (
    EvaluationRunOut,
    ListEvaluationsIn,
)
from planner.modules.evaluation.models import EvaluationRun


async def list_evaluations(
    session: AsyncSession,
    input: ListEvaluationsIn | None = None,
    *,
    actor_id: UUID | None = None,
    actor_role: str = "system",
) -> Page[EvaluationRunOut]:
    """List evaluation runs ordered by created_at desc with pagination."""
    if input is None:
        input = ListEvaluationsIn()

    count_stmt = select(func.count()).select_from(EvaluationRun)
    total = (await session.execute(count_stmt)).scalar() or 0

    offset = (input.page - 1) * input.page_size
    stmt = (
        select(EvaluationRun)
        .order_by(EvaluationRun.created_at.desc())
        .offset(offset)
        .limit(input.page_size)
    )
    result = await session.execute(stmt)
    runs = result.scalars().all()

    items = [EvaluationRunOut.model_validate(r, from_attributes=True) for r in runs]
    return build_page(items=items, total=total, page=input.page, page_size=input.page_size)


__all__ = ["list_evaluations"]
