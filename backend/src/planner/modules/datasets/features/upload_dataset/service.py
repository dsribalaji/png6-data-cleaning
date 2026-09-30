"""Upload dataset service implementing validation, storage, quarantine pre-check, and task dispatch."""

from __future__ import annotations

import io
import logging
import zipfile
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.core.config import settings
from planner.core.db import uuid7
from planner.core.events import DatasetUploadedPayload, EventType
from planner.core.outbox import emit, register_outbox_handler
from planner.core.ports.adapters import get_storage
from planner.core.ports.storage import raw_key
from planner.core.security import RequestPrincipal
from planner.modules.datasets.errors import DatasetsErrors
from planner.modules.datasets.features.upload_dataset.schemas import DatasetRead
from planner.modules.datasets.helpers import create_job
from planner.modules.datasets.models import Dataset, Job, QuarantineRecord

logger = logging.getLogger(__name__)

# Register outbox handler at import time per Backend.md contract
register_outbox_handler("dataset.uploaded", "planner.modules.datasets.tasks.ingest_dataset")


def _precheck_quarantine(
    file_name: str, data: bytes
) -> tuple[list[dict[str, str]], bool]:
    """Lightweight structural pre-check (pure Python, FR-044).

    Returns:
        (quarantine_records, is_completely_unreadable)
    """
    records: list[dict[str, str]] = []
    lower = file_name.lower()

    if lower.endswith(".xlsx"):
        # Excel files must start with the standard PK\x03\x04 zip local file header
        if not data.startswith(b"PK\x03\x04"):
            return [{"row_ref": "file", "reason": "Missing XLSX zip header (PK\\x03\\x04)"}], True

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                corrupted_member = zf.testzip()
                if corrupted_member:
                    records.append(
                        {
                            "row_ref": "archive",
                            "reason": f"Corrupt archive member: {corrupted_member}",
                        }
                    )
        except zipfile.BadZipFile as exc:
            return [{"row_ref": "file", "reason": f"Unreadable zip archive: {exc}"}], True
        except Exception as exc:
            logger.warning("Error inspecting xlsx zip structure: %s", exc)

        return records, False

    if lower.endswith(".csv"):
        if len(data) == 0:
            return [{"row_ref": "file", "reason": "Empty CSV file"}], True

        lines = data.splitlines()
        # Sniff rows for null bytes or undecodable byte sequences
        for idx, line in enumerate(lines[:500], start=1):
            if b"\x00" in line:
                records.append(
                    {
                        "row_ref": f"row {idx}",
                        "reason": "Null byte detected in CSV row",
                    }
                )
            try:
                line.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    line.decode("latin-1")
                    records.append(
                        {
                            "row_ref": f"row {idx}",
                            "reason": "Non-UTF-8 characters detected in CSV row",
                        }
                    )
                except Exception:
                    records.append(
                        {
                            "row_ref": f"row {idx}",
                            "reason": "Undecodable content in CSV row",
                        }
                    )

        return records, False

    return records, False


async def upload_dataset_service(
    file: UploadFile,
    session: AsyncSession,
    principal: RequestPrincipal,
    name: str | None = None,
) -> DatasetRead:
    """Validate, stream, save raw dataset, record quarantine, and enqueue ingest.

    ``name`` defaults to the file name (PRD S3).
    """
    file_name = file.filename or ""
    dataset_name = (name or "").strip() or file_name
    lower_name = file_name.lower()

    # 1. Enforce allowed extension (.xlsx or .csv)
    if not (lower_name.endswith(".xlsx") or lower_name.endswith(".csv")):
        raise DatasetsErrors.UNSUPPORTED_FILE_TYPE

    # 2. Enforce dataset name uniqueness
    stmt = select(Dataset).where(Dataset.name == dataset_name)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        raise DatasetsErrors.DATASET_NAME_TAKEN

    # 3. Stream upload and enforce size limit
    max_bytes = settings.upload_max_mb * 1024 * 1024
    content = bytearray()
    chunk_size = 64 * 1024  # 64 KB chunks
    while chunk := await file.read(chunk_size):
        content.extend(chunk)
        if len(content) > max_bytes:
            raise DatasetsErrors.file_too_large(settings.upload_max_mb)

    data = bytes(content)

    # 4. Quarantine structural pre-check
    quarantine_items, is_unreadable = _precheck_quarantine(file_name, data)
    if is_unreadable:
        raise DatasetsErrors.UNSUPPORTED_FILE_TYPE

    # 5. Stream upload to storage
    dataset_id = uuid7()
    object_key = raw_key(dataset_id, file_name)
    content_type = (
        file.content_type
        or (
            "text/csv"
            if lower_name.endswith(".csv")
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    )
    storage = get_storage()
    await storage.put(object_key, data, content_type=content_type)

    # 6. Database transaction: Dataset + Quarantine + Ingest Job + Outbox
    dataset = Dataset(
        id=dataset_id,
        name=dataset_name,
        source="upload",
        file_name=file_name,
        status="profiling",
        raw_object_key=object_key,
        uploaded_by=principal.user_id,
        version=1,
    )
    session.add(dataset)

    for item in quarantine_items:
        session.add(
            QuarantineRecord(
                dataset_id=dataset_id,
                row_ref=item["row_ref"],
                reason=item["reason"],
            )
        )

    job: Job = await create_job(session=session, dataset_id=dataset_id, type="ingest")

    await emit(
        session,
        EventType.DATASET_UPLOADED,
        DatasetUploadedPayload(dataset_id=dataset_id),
    )

    await session.commit()
    await session.refresh(dataset)

    # 7. Enqueue Celery ingest task lazily (async-safe: eager tasks run inline
    # in a worker thread so asyncio.run() works in demo mode).
    try:
        from planner.worker import dispatch_task

        await dispatch_task(
            "planner.modules.datasets.tasks.ingest_dataset",
            kwargs={"dataset_id": str(dataset_id), "job_id": str(job.id)},
            wait=False,  # ingest + profile can take a while; the row updates live
        )
    except Exception as exc:
        logger.warning("Could not enqueue Celery ingest task: %s", exc)

    # 8. Record audit event
    await record_audit(
            session=session,
        user_id=principal.user_id,
        user_role=principal.role,
        event_type="dataset.upload",
        object_type="dataset",
        object_id=str(dataset_id),
        details={"fileName": file_name, "fileSize": len(data)},
    )

    return DatasetRead.model_validate(dataset)
