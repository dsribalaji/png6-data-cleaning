"""Internal helper functions for dataset queries, jobs, and event replay."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import SessionLocal
from planner.core.errors import AppError
from planner.core.events import JobStatusPayload
from planner.core.realtime import publish_job_status
from planner.modules.datasets.models import Dataset, Job

logger = logging.getLogger(__name__)


async def get_dataset_or_404(session: AsyncSession, dataset_id: UUID) -> Dataset:
    """Fetch dataset by ID, raising AppError('NOT_FOUND') if missing."""
    dataset = await session.get(Dataset, dataset_id)
    if dataset is None:
        raise AppError("NOT_FOUND")
    return dataset


async def create_job(
    session: AsyncSession,
    dataset_id: UUID,
    type: str,
    plan_id: UUID | None = None,
) -> Job:
    """Create and persist a queued background job row."""
    job = Job(
        dataset_id=dataset_id,
        plan_id=plan_id,
        type=type,
        status="queued",
        progress_pct=0.0,
    )
    session.add(job)
    await session.flush()
    return job


async def update_job(
    session: AsyncSession,
    job_id: UUID,
    status: str | None = None,
    progress_pct: float | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    celery_task_id: str | None = None,
) -> Job:
    """Update job fields and publish JobStatusPayload on Redis channel jobs:{dataset_id}.

    Emits nothing to outbox (UI notification only, per Backend.md).
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise AppError("NOT_FOUND", f"Job {job_id} not found.")

    now = datetime.now(timezone.utc)
    if status is not None:
        job.status = status
        if status == "running" and job.started_at is None:
            job.started_at = now
        elif status in ("succeeded", "failed"):
            if job.started_at is None:
                job.started_at = now
            job.finished_at = now

    if progress_pct is not None:
        job.progress_pct = max(0.0, min(100.0, float(progress_pct)))
    if error_code is not None:
        job.error_code = error_code
    if error_message is not None:
        job.error_message = error_message
    if celery_task_id is not None:
        job.celery_task_id = celery_task_id

    await session.flush()

    # Publish real-time status update to Redis channel jobs:{dataset_id}
    msg = job.error_message or f"Job {job.type} {job.status}"
    payload = JobStatusPayload(
        job_id=job.id,
        type=job.type,
        status=job.status,
        progress_pct=job.progress_pct,
        message=msg,
        plan_id=job.plan_id,
    )
    try:
        await publish_job_status(job.dataset_id, payload)
    except Exception as exc:
        logger.warning(
            "Failed to publish job status for job %s on dataset %s: %s",
            job.id,
            job.dataset_id,
            exc,
        )

    return job


async def replay_job_events(
    dataset_id: UUID,
    last_event_id: str | None = None,
    session_factory: Any = SessionLocal,
) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
    """Read jobs rows for the dataset and yield (event_id, data_dict).

    If last_event_id is given, only yields rows with created_at greater than that job's created_at.
    """
    async with session_factory() as session:
        cutoff_time = None
        if last_event_id:
            try:
                ref_uuid = UUID(last_event_id)
                ref_job = await session.get(Job, ref_uuid)
                if ref_job is not None:
                    cutoff_time = ref_job.created_at
            except (ValueError, TypeError):
                cutoff_time = None

        stmt = select(Job).where(Job.dataset_id == dataset_id)
        if cutoff_time is not None:
            stmt = stmt.where(Job.created_at > cutoff_time)
        stmt = stmt.order_by(Job.created_at.asc())

        result = await session.execute(stmt)
        jobs = result.scalars().all()

        for j in jobs:
            data: dict[str, Any] = {
                "jobId": str(j.id),
                "type": j.type,
                "status": j.status,
                "progressPct": float(j.progress_pct),
                "message": j.error_message or f"Job {j.type} {j.status}",
            }
            if j.plan_id is not None:
                data["planId"] = str(j.plan_id)
            yield str(j.id), data
