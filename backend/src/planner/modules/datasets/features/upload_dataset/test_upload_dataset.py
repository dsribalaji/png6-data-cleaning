"""Service-level unit tests for upload_dataset feature."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.config import settings
from planner.core.db import Base, uuid7
from planner.core.errors import AppError
from planner.core.outbox import OutboxEvent
from planner.core.security import RequestPrincipal
from planner.modules.datasets.features.upload_dataset.service import upload_dataset_service
from planner.modules.datasets.models import Dataset, Job, QuarantineRecord


class InMemoryStorage:
    """In-memory stub implementing StoragePort for testing."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise AppError("NOT_FOUND", f"Object {key} not found")
        return self.objects[key]

    async def presigned_get_url(self, key: str, expires_seconds: int = 900) -> str:
        return f"http://mock-storage/{key}"

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def list(self, prefix: str) -> list[str]:
        return [k for k in self.objects if k.startswith(prefix)]

    put_object = put
    get_object = get


@pytest.fixture
async def async_session() -> AsyncSession:
    """Provide an in-memory SQLite session with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def mock_storage(monkeypatch: pytest.MonkeyPatch) -> InMemoryStorage:
    storage = InMemoryStorage()
    monkeypatch.setattr("planner.core.ports.adapters._storage", storage)
    return storage


@pytest.fixture
def principal() -> RequestPrincipal:
    return RequestPrincipal(user_id=uuid7(), role="data_engineer")


@pytest.mark.asyncio
async def test_upload_dataset__valid_csv__creates_dataset_job_and_outbox(
    async_session: AsyncSession,
    mock_storage: InMemoryStorage,
    principal: RequestPrincipal,
) -> None:
    csv_bytes = b"invoice_id,amount,vendor\nINV001,100.50,Acme Corp\nINV002,200.00,Beta LLC"
    upload_file = UploadFile(file=io.BytesIO(csv_bytes), filename="invoices.csv")

    with patch("planner.worker.dispatch_task", new_callable=AsyncMock) as mock_send_task:
        result = await upload_dataset_service(
            file=upload_file,
            session=async_session,
            principal=principal,
        )

    # 1. Check returned schema
    assert result.name == "invoices.csv"
    assert result.file_name == "invoices.csv"
    assert result.model_dump(by_alias=True)["fileName"] == "invoices.csv"
    assert result.source == "upload"
    assert result.status == "profiling"
    assert result.id is not None

    # 2. Verify dataset in database
    db_dataset = await async_session.get(Dataset, result.id)
    assert db_dataset is not None
    assert db_dataset.name == "invoices.csv"
    assert db_dataset.uploaded_by == principal.user_id

    # 3. Verify job created in database
    job_stmt = select(Job).where(Job.dataset_id == result.id)
    job = (await async_session.execute(job_stmt)).scalar_one_or_none()
    assert job is not None
    assert job.type == "ingest"
    assert job.status == "queued"

    # 4. Verify outbox event emitted
    outbox_stmt = select(OutboxEvent).where(OutboxEvent.event_type == "dataset.uploaded")
    outbox_event = (await async_session.execute(outbox_stmt)).scalar_one_or_none()
    assert outbox_event is not None
    assert outbox_event.payload.get("datasetId") == str(result.id)

    # 5. Verify file written to storage
    expected_key = f"raw/{result.id}/invoices.csv"
    assert await mock_storage.exists(expected_key)
    assert await mock_storage.get(expected_key) == csv_bytes

    # 6. Verify Celery task was dispatched
    mock_send_task.assert_called_once_with(
        "planner.modules.datasets.tasks.ingest_dataset",
        kwargs={"dataset_id": str(result.id), "job_id": str(job.id)},
        wait=False,
    )


@pytest.mark.asyncio
async def test_upload_dataset__unsupported_extension__raises_unsupported_file_type(
    async_session: AsyncSession,
    mock_storage: InMemoryStorage,
    principal: RequestPrincipal,
) -> None:
    upload_file = UploadFile(file=io.BytesIO(b"data"), filename="document.pdf")

    with pytest.raises(AppError) as exc_info:
        await upload_dataset_service(
            file=upload_file,
            session=async_session,
            principal=principal,
        )

    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"
    assert exc_info.value.status == 400


@pytest.mark.asyncio
async def test_upload_dataset__duplicate_name__raises_dataset_name_taken(
    async_session: AsyncSession,
    mock_storage: InMemoryStorage,
    principal: RequestPrincipal,
) -> None:
    # Seed an existing dataset with the same name
    existing = Dataset(
        id=uuid7(),
        name="duplicate.csv",
        source="upload",
        file_name="duplicate.csv",
        status="profiling",
    )
    async_session.add(existing)
    await async_session.commit()

    upload_file = UploadFile(file=io.BytesIO(b"a,b\n1,2"), filename="duplicate.csv")

    with pytest.raises(AppError) as exc_info:
        await upload_dataset_service(
            file=upload_file,
            session=async_session,
            principal=principal,
        )

    assert exc_info.value.code == "DATASET_NAME_TAKEN"
    assert exc_info.value.status == 409


@pytest.mark.asyncio
async def test_upload_dataset__concurrent_same_name__raises_dataset_name_taken(
    async_session: AsyncSession,
    mock_storage: InMemoryStorage,
    principal: RequestPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Another upload commits the same name after our existence check ran.
    async_session.add(
        Dataset(
            id=uuid7(), name="race.csv", source="upload", file_name="race.csv", status="profiling"
        )
    )
    await async_session.commit()
    real_execute = async_session.execute
    calls = {"n": 0}

    async def first_check_misses(stmt, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        result = await real_execute(stmt, *args, **kwargs)
        if calls["n"] == 1:  # the name-uniqueness SELECT
            result.scalar_one_or_none = lambda: None  # type: ignore[method-assign]
        return result

    monkeypatch.setattr(async_session, "execute", first_check_misses)
    upload_file = UploadFile(file=io.BytesIO(b"a,b\n1,2"), filename="race.csv")

    with pytest.raises(AppError) as exc_info:
        await upload_dataset_service(file=upload_file, session=async_session, principal=principal)

    assert exc_info.value.code == "DATASET_NAME_TAKEN"


@pytest.mark.asyncio
async def test_upload_dataset__file_exceeds_max_mb__raises_file_too_large(
    async_session: AsyncSession,
    mock_storage: InMemoryStorage,
    principal: RequestPrincipal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Set limit to 1 MB for testing
    monkeypatch.setattr(settings, "upload_max_mb", 1)

    oversized_data = b"x" * (1 * 1024 * 1024 + 100)
    upload_file = UploadFile(file=io.BytesIO(oversized_data), filename="large.csv")

    with pytest.raises(AppError) as exc_info:
        await upload_dataset_service(
            file=upload_file,
            session=async_session,
            principal=principal,
        )

    assert exc_info.value.code == "FILE_TOO_LARGE"
    assert exc_info.value.status == 413


@pytest.mark.asyncio
async def test_upload_dataset__csv_with_null_bytes__adds_quarantine_records_and_succeeds(
    async_session: AsyncSession,
    mock_storage: InMemoryStorage,
    principal: RequestPrincipal,
) -> None:
    csv_with_null = b"id,val\n1,clean\n2,bad\x00data\n3,good"
    upload_file = UploadFile(file=io.BytesIO(csv_with_null), filename="partially_corrupt.csv")

    with patch("planner.worker.celery_app.send_task"):
        result = await upload_dataset_service(
            file=upload_file,
            session=async_session,
            principal=principal,
        )

    assert result.name == "partially_corrupt.csv"

    # Verify quarantine records exist for row 3 (header is row 1, row 2 has null byte)
    q_stmt = select(QuarantineRecord).where(QuarantineRecord.dataset_id == result.id)
    records = (await async_session.execute(q_stmt)).scalars().all()
    assert len(records) > 0
    assert any("Null byte" in r.reason for r in records)


@pytest.mark.asyncio
async def test_upload_dataset__valid_xlsx__succeeds(
    async_session: AsyncSession,
    mock_storage: InMemoryStorage,
    principal: RequestPrincipal,
) -> None:
    # Build a minimal valid zip file
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", b"<Types></Types>")
    xlsx_bytes = buf.getvalue()

    upload_file = UploadFile(file=io.BytesIO(xlsx_bytes), filename="workbook.xlsx")

    with patch("planner.worker.celery_app.send_task"):
        result = await upload_dataset_service(
            file=upload_file,
            session=async_session,
            principal=principal,
        )

    assert result.name == "workbook.xlsx"
    assert result.source == "upload"


@pytest.mark.asyncio
async def test_upload_dataset__invalid_xlsx_header__raises_unsupported_file_type(
    async_session: AsyncSession,
    mock_storage: InMemoryStorage,
    principal: RequestPrincipal,
) -> None:
    # Invalid XLSX not starting with PK\x03\x04
    corrupt_xlsx = b"NOT_A_ZIP_HEADER_DATA"
    upload_file = UploadFile(file=io.BytesIO(corrupt_xlsx), filename="fake.xlsx")

    with pytest.raises(AppError) as exc_info:
        await upload_dataset_service(
            file=upload_file,
            session=async_session,
            principal=principal,
        )

    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"
    assert exc_info.value.status == 400
