"""Service for creating and enqueuing evaluation runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Audit logging function: record_audit is currently a stub owned by W1
from planner.core.audit import record_audit
from planner.modules.evaluation.errors import BENCHMARK_SET_NOT_FOUND
from planner.modules.evaluation.features.create_evaluation.schemas import (
    CreateEvaluationIn,
    CreateEvaluationOut,
)
from planner.modules.evaluation.models import BenchmarkSet, EvaluationRun


async def create_evaluation(
    session: AsyncSession,
    input: CreateEvaluationIn | None = None,
    *,
    actor_id: UUID | None = None,
    actor_role: str = "system",
) -> CreateEvaluationOut:
    """Create an evaluation run, enqueue the background task, and record audit."""
    if input is None:
        input = CreateEvaluationIn()

    if input.benchmark_set_id is not None:
        stmt = select(BenchmarkSet).where(BenchmarkSet.id == input.benchmark_set_id)
        result = await session.execute(stmt)
        bset = result.scalar_one_or_none()
        if bset is None:
            raise BENCHMARK_SET_NOT_FOUND
        benchmark_set_id = bset.id
    elif input.benchmark_set:
        stmt = select(BenchmarkSet).where(BenchmarkSet.name == input.benchmark_set)
        result = await session.execute(stmt)
        bset = result.scalar_one_or_none()
        if bset is None:
            bset = BenchmarkSet(
                name=input.benchmark_set,
                description=f"Benchmark set '{input.benchmark_set}'",
                object_keys=[],
            )
            session.add(bset)
            await session.flush()
        benchmark_set_id = bset.id
    else:
        # Lazy: public.py imports this feature's router (circular at module load).
        from planner.modules.evaluation.public import ensure_default_benchmark_set

        bset = await ensure_default_benchmark_set(session)
        benchmark_set_id = bset.id

    run = EvaluationRun(
        benchmark_set_id=benchmark_set_id,
        model_config_id=input.model_config_id,
        status="pending",
    )
    session.add(run)
    await session.flush()
    await session.commit()
    await session.refresh(run)

    # Import inside the service function to avoid hard import cycles
    from planner.modules.evaluation import tasks as _tasks

    _tasks.run_evaluation.delay(str(run.id))

    # Audit: call record_audit per specification (stub owned by worker W1)
    await record_audit(
        session,
        user_id=actor_id,
        user_role=actor_role,
        event_type="evaluation.requested",
        object_type="evaluation_run",
        object_id=str(run.id),
        details={
            "benchmarkSetId": str(run.benchmark_set_id),
            "modelConfigId": str(run.model_config_id) if run.model_config_id else None,
        },
    )

    return CreateEvaluationOut(id=run.id, status=run.status)
