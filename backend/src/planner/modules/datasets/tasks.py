"""Celery tasks for datasets module (ingestion and n8n folder polling, Backend.md)."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from planner.core.config import settings
from planner.core.db import SessionLocal, uuid7
from planner.core.events import (
    DatasetIngestedPayload,
    DatasetUploadedPayload,
    EventType,
    JobFailedPayload,
)
from planner.core.outbox import emit, register_outbox_handler
from planner.core.ports.adapters import get_storage
from planner.core.ports.storage import raw_key
from planner.modules.datasets.helpers import create_job, update_job
from planner.modules.datasets.models import Dataset, Job, QuarantineRecord

logger = logging.getLogger(__name__)

# Register outbox handler mapping per contract
register_outbox_handler("dataset.uploaded", "planner.modules.datasets.tasks.ingest_dataset")


async def _async_ingest_dataset(task_self: Any, dataset_id: str, job_id: str) -> None:
    """Async implementation of dataset ingestion."""
    d_uuid = UUID(dataset_id)
    j_uuid = UUID(job_id)

    # 1. Row-lock the job row and check status (idempotency)
    async with SessionLocal() as session:
        stmt = select(Job).where(Job.id == j_uuid)
        if settings.database_url.startswith("postgresql"):
            stmt = stmt.with_for_update()

        result = await session.execute(stmt)
        job = result.scalar_one_or_none()
        if job is None:
            logger.warning("Ingest job %s not found; aborting", job_id)
            return

        if job.status == "succeeded":
            logger.info("Job %s already succeeded; idempotent exit", job_id)
            return

        await update_job(
            session=session,
            job_id=j_uuid,
            status="running",
            progress_pct=10.0,
        )
        await session.commit()

    # 2. Lazily import W2 engine ingest function
    try:
        from planner.engine.ingest import ingest_dataset_file
    except ImportError as err:
        # Honest TODO: Engine ingest module belongs to W2 slice and is not yet implemented
        async with SessionLocal() as err_session:
            await update_job(
                session=err_session,
                job_id=j_uuid,
                status="failed",
                error_code="ENGINE_NOT_STARTED",
                error_message="Engine ingest module is not implemented yet (W2 slice).",
            )
            await emit(
                err_session,
                EventType.JOB_FAILED,
                JobFailedPayload(
                    job_id=j_uuid,
                    error_code="ENGINE_NOT_STARTED",
                    error_message="Engine ingest module is not implemented yet (W2 slice).",
                ),
            )
            await err_session.commit()
        raise RuntimeError(
            "ENGINE_NOT_STARTED: planner.engine.ingest is not yet implemented (W2 slice)"
        ) from err

    # 3. Execute engine ingest logic
    async with SessionLocal() as session:
        dataset = await session.get(Dataset, d_uuid)
        if dataset is None:
            raise RuntimeError(f"Dataset {d_uuid} not found")

        if inspect.iscoroutinefunction(ingest_dataset_file):
            ingest_result = await ingest_dataset_file(dataset.raw_object_key)
        else:
            ingest_result = ingest_dataset_file(dataset.raw_object_key)

        dataset.row_count = getattr(ingest_result, "row_count", None)
        dataset.column_count = getattr(ingest_result, "column_count", None)
        # Integration 2026-09-30: the engine now returns the Parquet key that
        # profiling/execution read back.
        ingested_key = getattr(ingest_result, "ingested_object_key", None)
        if ingested_key:
            dataset.ingested_object_key = ingested_key
        # FR-044: every row the engine quarantined is recorded with its reason.
        for row_ref, reason in getattr(ingest_result, "quarantine", []):
            session.add(QuarantineRecord(dataset_id=d_uuid, row_ref=row_ref, reason=reason))
        # Stays "profiling": the profile + rules tasks chained below flip it to "profiled".
        dataset.ingested_at = datetime.now(UTC)

        await update_job(
            session=session,
            job_id=j_uuid,
            status="succeeded",
            progress_pct=100.0,
        )
        await emit(
            session,
            EventType.DATASET_INGESTED,
            DatasetIngestedPayload(dataset_id=d_uuid),
        )
        await session.commit()

        # Integration 2026-09-30: chain into profiling. A fresh profile job is
        # created so progress/events stay attributable per phase.
        try:
            from planner.worker import send_task_eager_aware

            async with SessionLocal() as _profile_session:
                _profile_job = await create_job(
                    session=_profile_session, dataset_id=d_uuid, type="profile"
                )
                await _profile_session.commit()
                _profile_job_id = str(_profile_job.id)
            send_task_eager_aware(
                "planner.profile_dataset",
                args=[str(d_uuid), _profile_job_id],
                queue="profile",
            )
        except Exception as exc:  # noqa: BLE001 - ingest already succeeded
            logger.warning("Could not enqueue profile task for %s: %s", d_uuid, exc)


@shared_task(
    name="planner.modules.datasets.tasks.ingest_dataset",
    bind=True,
    acks_late=True,
    max_retries=3,
)
def ingest_dataset(self: Any, dataset_id: str, job_id: str) -> None:
    """Celery task: Ingest dataset file, update job status, and emit outbox event."""
    try:
        asyncio.run(_async_ingest_dataset(self, dataset_id, job_id))
    except RuntimeError as err:
        if "ENGINE_NOT_STARTED" in str(err):
            raise
        _handle_retry_or_fail(self, err, job_id)
    except Exception as exc:  # noqa: BLE001 -- Celery task boundary: convert any failure to retry/fail handling
        _handle_retry_or_fail(self, exc, job_id)


def _handle_retry_or_fail(task: Any, exc: Exception, job_id: str) -> None:
    """Handle Celery task retries with exponential backoff (10s, 60s, 300s)."""
    retries = getattr(task.request, "retries", 0) if hasattr(task, "request") else 0
    intervals = [10, 60, 300]
    if retries < len(intervals) and hasattr(task, "retry"):
        countdown = intervals[retries]
        raise task.retry(exc=exc, countdown=countdown)

    # Retries exhausted: mark job failed and emit job.failed
    async def _mark_failed() -> None:
        async with SessionLocal() as session:
            j_uuid = UUID(job_id)
            await update_job(
                session=session,
                job_id=j_uuid,
                status="failed",
                error_code="INTERNAL",
                error_message=str(exc),
            )
            await emit(
                session,
                EventType.JOB_FAILED,
                JobFailedPayload(
                    job_id=j_uuid,
                    error_code="INTERNAL",
                    error_message=str(exc),
                ),
            )
            await session.commit()

    try:
        asyncio.run(_mark_failed())
    except Exception as err:  # noqa: BLE001 -- failure bookkeeping must not mask the original error
        logger.error("Failed to mark job %s as failed: %s", job_id, err)
    raise exc


async def _async_poll_n8n_folder() -> int:
    """Scan n8n output directory for new CSV/XLSX files and enqueue ingestion."""
    folder = Path(settings.n8n_folder_path)
    folder.mkdir(parents=True, exist_ok=True)

    polled_count = 0
    candidates = [
        p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".xlsx", ".csv")
    ]

    for file_path in candidates:
        file_name = file_path.name
        try:
            async with SessionLocal() as session:
                # Match by file_name and source='n8n_folder'
                stmt = select(Dataset).where(
                    Dataset.file_name == file_name,
                    Dataset.source == "n8n_folder",
                )
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing is not None:
                    continue

                # Also verify name uniqueness
                name_stmt = select(Dataset).where(Dataset.name == file_name)
                if (await session.execute(name_stmt)).scalar_one_or_none() is not None:
                    continue

                data = file_path.read_bytes()
                dataset_id = uuid7()
                obj_key = raw_key(dataset_id, file_name)
                storage = get_storage()
                await storage.put(obj_key, data)

                dataset = Dataset(
                    id=dataset_id,
                    name=file_name,
                    source="n8n_folder",
                    file_name=file_name,
                    status="profiling",
                    raw_object_key=obj_key,
                    version=1,
                )
                session.add(dataset)

                job = await create_job(session=session, dataset_id=dataset_id, type="ingest")

                await emit(
                    session,
                    EventType.DATASET_UPLOADED,
                    DatasetUploadedPayload(dataset_id=dataset_id),
                )
                await session.commit()
                polled_count += 1

                try:
                    from planner.worker import send_task_eager_aware

                    send_task_eager_aware(
                        "planner.modules.datasets.tasks.ingest_dataset",
                        kwargs={"dataset_id": str(dataset_id), "job_id": str(job.id)},
                    )
                except Exception as exc:  # noqa: BLE001 -- enqueue is best-effort; file stays for next poll
                    logger.warning("Failed to enqueue ingest task for %s: %s", file_name, exc)
        except Exception:
            logger.exception("Error processing n8n folder file %s", file_name)

    return polled_count


@shared_task(name="planner.modules.datasets.tasks.poll_n8n_folder", bind=True)
def poll_n8n_folder(self: Any = None) -> int:
    """Celery task: Poll configured n8n directory for newly placed files."""
    return asyncio.run(_async_poll_n8n_folder())


def register_tasks(celery_app: Any) -> None:
    """Register tasks on the Celery application for uniform interface.

    ``shared_task`` registers each task on every finalized Celery app, so
    finalizing here is enough. The task objects must NOT be passed to
    ``registry.register``: they are lazy Proxies, and storing a Proxy in the
    registry makes every later attribute access on the task recurse infinitely.
    """
    celery_app.tasks  # noqa: B018 - accessing the registry finalizes the app
