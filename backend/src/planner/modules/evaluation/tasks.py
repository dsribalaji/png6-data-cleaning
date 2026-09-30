"""Celery tasks for the evaluation module (Backend.md)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from planner.core.db import SessionLocal
from planner.core.events import EventType
from planner.core.outbox import add_event
from planner.modules.evaluation import adversarial
from planner.modules.evaluation.models import EvaluationRun
# NOTE: W1 must ensure this module is imported at worker startup so tasks are registered.
from planner.worker import celery_app


@celery_app.task(
    name="evaluation.run_evaluation",
    queue="eval",
    soft_time_limit=120,
    autoretry_for=(Exception,),
    retry_backoff=10,
    max_retries=3,
)
def run_evaluation(run_id: str) -> dict[str, Any]:
    """Execute evaluation run synchronously wrapping the async implementation."""
    return asyncio.run(_run_evaluation_async(run_id))


async def _run_evaluation_async(
    run_id: str,
    *,
    session_factory: Any = None,
) -> dict[str, Any]:
    """Asynchronous worker implementation for evaluation execution.

    Loads run, sets status to running, runs adversarial suite, records scores,
    emits evaluation.completed outbox event, and marks succeeded.
    Idempotent: exits early if run is missing or already succeeded or running.
    """
    try:
        u_run_id = UUID(str(run_id))
    except (ValueError, TypeError):
        return {"status": "invalid_id", "runId": run_id}

    maker = session_factory or SessionLocal
    async with maker() as session:
        stmt = select(EvaluationRun).where(EvaluationRun.id == u_run_id)
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()

        # Idempotency / early exit checks:
        if run is None or run.status not in ("pending", "failed"):
            return {
                "status": getattr(run, "status", "not_found"),
                "runId": str(run_id),
                "early_exit": True,
            }

        now = datetime.now(timezone.utc)
        run.status = "running"
        run.started_at = now
        run.error_message = None
        await session.flush()
        await session.commit()

        try:
            scores = adversarial.run_adversarial_suite()
            finished_now = datetime.now(timezone.utc)
            run.scores = scores
            run.status = "succeeded"
            run.finished_at = finished_now
            await add_event(
                session,
                EventType.EVALUATION_COMPLETED,
                {"evaluationId": str(run.id), "passed": scores["passed"]},
            )
            await session.commit()
            return scores
        except Exception as exc:
            finished_now = datetime.now(timezone.utc)
            run.status = "failed"
            run.error_message = str(exc)[:500]
            run.finished_at = finished_now
            await session.commit()
            raise


__all__ = ["_run_evaluation_async", "run_evaluation"]
