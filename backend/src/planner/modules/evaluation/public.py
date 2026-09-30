"""The ONLY import surface other modules may use (Backend.md)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.evaluation.errors import EVALUATION_NOT_FOUND
from planner.modules.evaluation.models import BenchmarkSet, EvaluationRun

DEFAULT_BENCHMARK_SET_NAME = "adversarial-v1"
DEFAULT_BENCHMARK_SET_DESCRIPTION = (
    "Adversarial fixtures: malformed rows, injected instructions, 95%-sparse columns. "
    "Fixtures are generated in-code by adversarial.py."
)


async def get_run(session: AsyncSession, run_id: UUID) -> EvaluationRun:
    """Retrieve an evaluation run by ID, raising EVALUATION_NOT_FOUND if missing."""
    stmt = select(EvaluationRun).where(EvaluationRun.id == run_id)
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        raise EVALUATION_NOT_FOUND
    return run


async def ensure_default_benchmark_set(session: AsyncSession) -> BenchmarkSet:
    """Get or create the default 'adversarial-v1' benchmark set."""
    stmt = select(BenchmarkSet).where(BenchmarkSet.name == DEFAULT_BENCHMARK_SET_NAME)
    result = await session.execute(stmt)
    bset = result.scalar_one_or_none()
    if bset is None:
        bset = BenchmarkSet(
            name=DEFAULT_BENCHMARK_SET_NAME,
            description=DEFAULT_BENCHMARK_SET_DESCRIPTION,
            object_keys=[],
        )
        session.add(bset)
        await session.flush()
    return bset


__all__ = [
    "DEFAULT_BENCHMARK_SET_DESCRIPTION",
    "DEFAULT_BENCHMARK_SET_NAME",
    "BenchmarkSet",
    "EvaluationRun",
    "ensure_default_benchmark_set",
    "get_run",
]
