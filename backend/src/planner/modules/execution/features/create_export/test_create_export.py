"""Unit tests for create_export feature."""

from __future__ import annotations

import io
import sys
import tempfile
import types
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import polars as pl
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.errors import AppError
from planner.modules.execution.features.create_export.service import create_export
from planner.modules.execution.models import ExportRow, PipelineVersion
from planner.modules.execution.schemas import ExportRequest


@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    # SQLite schemas are mapped in core.db; conftest registers every model.

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_export_invalid_format(test_session: AsyncSession):
    plan_id = uuid.uuid4()
    req = ExportRequest(format="pdf")
    with pytest.raises(AppError) as exc_info:
        await create_export(test_session, plan_id, req)
    assert exc_info.value.code == "INVALID_FORMAT"
    assert exc_info.value.status == 400


@pytest.mark.asyncio
async def test_create_export_no_executed_version(test_session: AsyncSession):
    plan_id = uuid.uuid4()
    req = ExportRequest(format="xlsx")
    with pytest.raises(AppError) as exc_info:
        await create_export(test_session, plan_id, req)
    assert exc_info.value.code == "NO_EXECUTED_VERSION"
    assert exc_info.value.status == 409


@pytest.mark.asyncio
async def test_create_export_validation_blocked(test_session: AsyncSession, monkeypatch):
    plan_id = uuid.uuid4()
    v1 = PipelineVersion(
        id=uuid.uuid4(),
        plan_id=plan_id,
        version_no=1,
        step_id=uuid.uuid4(),
        snapshot_object_key=f"snapshots/{plan_id}/v1.parquet",
        inverse_operation={"op": "restore_cells"},
    )
    test_session.add(v1)
    await test_session.commit()

    mock_val = types.ModuleType("planner.modules.validation.public")
    mock_val.latest_validation_passed = AsyncMock(return_value=False)
    monkeypatch.setitem(sys.modules, "planner.modules.validation.public", mock_val)

    req = ExportRequest(format="xlsx")
    with pytest.raises(AppError) as exc_info:
        await create_export(test_session, plan_id, req)
    assert exc_info.value.code == "EXPORT_BLOCKED_TESTS_FAILED"
    assert exc_info.value.status == 409


@pytest.mark.asyncio
async def test_create_export_csv_and_xlsx_success(
    test_session: AsyncSession, monkeypatch, tmp_path: Path
):
    plan_id = uuid.uuid4()
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path))

    # Create dummy parquet snapshot
    df = pl.DataFrame({"invoice_id": [101, 102], "amount": [50.0, 75.5]})
    snapshot_dir = tmp_path / "snapshots" / str(plan_id)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(snapshot_dir / "v1.parquet")

    # Side table
    side_df = pl.DataFrame({"item_id": [1, 2], "desc": ["Widget A", "Widget B"]})
    side_df.write_parquet(snapshot_dir / "v1__LineItems.parquet")

    v1 = PipelineVersion(
        id=uuid.uuid4(),
        plan_id=plan_id,
        version_no=1,
        step_id=uuid.uuid4(),
        snapshot_object_key=f"snapshots/{plan_id}/v1.parquet",
        inverse_operation={"op": "restore_cells"},
    )
    test_session.add(v1)
    await test_session.commit()

    # Mock validation pass
    mock_val = types.ModuleType("planner.modules.validation.public")
    mock_val.latest_validation_passed = AsyncMock(return_value=True)
    monkeypatch.setitem(sys.modules, "planner.modules.validation.public", mock_val)

    # 1. Test CSV export
    req_csv = ExportRequest(format="csv")
    resp_csv = await create_export(test_session, plan_id, req_csv)
    assert resp_csv.download_url.endswith(f"exports/{plan_id}/v1/tables.csv.zip")
    assert resp_csv.expires_at is not None

    # Check export row
    rows = (
        await test_session.execute(
            select(ExportRow).where(ExportRow.plan_id == plan_id, ExportRow.format == "csv")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].version_no == 1

    # 2. Test XLSX export
    req_xlsx = ExportRequest(format="xlsx")
    resp_xlsx = await create_export(test_session, plan_id, req_xlsx)
    assert resp_xlsx.download_url.endswith(f"exports/{plan_id}/v1/tables.xlsx")

    rows_xlsx = (
        await test_session.execute(
            select(ExportRow).where(ExportRow.plan_id == plan_id, ExportRow.format == "xlsx")
        )
    ).scalars().all()
    assert len(rows_xlsx) == 1
    assert rows_xlsx[0].version_no == 1

    # CSV zip carries every table; the workbook has one sheet per table
    import zipfile
    import openpyxl

    zf = zipfile.ZipFile(tmp_path / "exports" / str(plan_id) / "v1" / "tables.csv.zip")
    assert sorted(zf.namelist()) == ["LineItems.csv", "main.csv"]
    wb = openpyxl.load_workbook(tmp_path / "exports" / str(plan_id) / "v1" / "tables.xlsx")
    assert wb.sheetnames == ["main", "LineItems"]
