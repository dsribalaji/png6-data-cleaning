"""Service for retrieving evaluation run detail."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.evaluation.errors import EVALUATION_NOT_FOUND
from planner.modules.evaluation.features.get_evaluation.schemas import (
    EvaluationRunOut,
    GetEvaluationIn,
)
from planner.modules.evaluation.models import EvaluationRun


async def get_evaluation(
    session: AsyncSession,
    input: GetEvaluationIn | UUID,
    *,
    actor_id: UUID | None = None,
    actor_role: str = "system",
) -> EvaluationRunOut:
    """Retrieve an evaluation run by ID, raising EVALUATION_NOT_FOUND if missing."""
    run_id = input.run_id if isinstance(input, GetEvaluationIn) else input
    stmt = select(EvaluationRun).where(EvaluationRun.id == run_id)
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        raise EVALUATION_NOT_FOUND
    return EvaluationRunOut.model_validate(run, from_attributes=True)


__all__ = ["get_evaluation"]
