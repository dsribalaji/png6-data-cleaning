"""Tests for validation module celery tasks."""

from __future__ import annotations

import sys
import types
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import polars as pl
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.outbox import OutboxEvent
from planner.modules.validation.models import ReconciliationRow, TestCaseRow, TestRunRow
from planner.modules.validation.tasks import _async_generate_tests, _async_run_validation


@pytest.fixture
async def setup_db(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path))
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    # SQLite schemas are mapped away in core.db; all models are registered by conftest.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("planner.modules.validation.tasks.SessionLocal", session_factory)

    async with session_factory() as session:
        yield session, tmp_path

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_generate_tests_task(setup_db, monkeypatch):
    session, _ = setup_db
    plan_id = uuid.uuid4()
    job_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    mock_plan = types.SimpleNamespace(id=plan_id, dataset_id=dataset_id, status="approved")
    steps = [
        {
            "id": uuid.uuid4(),
            "step_no": 1,
            "operation": "replace_value",
            "parameters": {"column": "supplier_name", "mapping": {"Beta": "Alpha"}},
        },
        {
            "id": uuid.uuid4(),
            "step_no": 2,
            "operation": "fill_missing",
            "parameters": {"column": "vat_number", "value": "UNKNOWN"},
        },
    ]

    mock_planning = types.ModuleType("planner.modules.planning.public")
    mock_planning.get_plan_row = AsyncMock(return_value=mock_plan)
    mock_planning.get_decided_steps = AsyncMock(return_value=steps)
    monkeypatch.setitem(sys.modules, "planner.modules.planning.public", mock_planning)

    mock_prof = types.ModuleType("planner.modules.profiling.public")
    mock_prof.get_column_profile_rows = AsyncMock(
        return_value=[
            {
                "name": "supplier_name",
                "physical_type": "String",
                "semantic_type": "category",
                "null_count": 0,
                "null_pct": 0.0,
                "distinct_count": 2,
            },
            {
                "name": "vat_number",
                "physical_type": "String",
                "semantic_type": "identifier",
                "null_count": 5,
                "null_pct": 0.5,
                "distinct_count": 5,
            },
        ]
    )
    monkeypatch.setitem(sys.modules, "planner.modules.profiling.public", mock_prof)

    with patch("planner.modules.validation.tasks.send_task_eager_aware") as mock_send_task:
        res = await _async_generate_tests(str(plan_id), str(job_id))
        assert res["tests"] >= 2

        mock_send_task.assert_called_once_with(
            "planner.execute_plan",
            args=[str(plan_id), str(job_id)],
            queue="execute",
        )

        # Check generated test case rows in DB
        rows = (
            await session.execute(
                select(TestCaseRow).where(TestCaseRow.plan_id == plan_id)
            )
        ).scalars().all()
        assert len(rows) >= 2

        # Idempotency check: running again should return already_generated
        res_idempotent = await _async_generate_tests(str(plan_id), str(job_id))
        assert res_idempotent["status"] == "already_generated"


@pytest.mark.asyncio
async def test_run_validation_task(setup_db, monkeypatch, tmp_path: Path):
    session, _ = setup_db
    plan_id = uuid.uuid4()
    job_id = uuid.uuid4()

    # Create snapshot files: v0 and v1
    v0_df = pl.DataFrame({
        "supplier_name": ["Alpha", "Beta"],
        "line_items": ['[{"amount": 50.0}]', '[{"amount": 100.0}]'],
    })
    v0_path = tmp_path / "snapshots" / str(plan_id) / "v0.parquet"
    v0_path.parent.mkdir(parents=True, exist_ok=True)
    v0_df.write_parquet(v0_path)

    v1_df = pl.DataFrame({
        "supplier_name": ["Alpha", "Alpha"],
        "line_items": [1, 1],
    })
    v1_path = tmp_path / "snapshots" / str(plan_id) / "v1.parquet"
    v1_df.write_parquet(v1_path)

    # Side table for line_items
    side_df = pl.DataFrame({"amount": [50.0, 100.0]})
    side_path = tmp_path / "snapshots" / str(plan_id) / "v1__LineItems.parquet"
    side_df.write_parquet(side_path)

    # Insert a test case
    tc = TestCaseRow(
        id=uuid.uuid4(),
        plan_id=plan_id,
        type="unit",
        target_step_id=None,
        name="no_nulls_supplier_name",
        definition={"check": "no_nulls", "column": "supplier_name", "table": "main"},
    )
    session.add(tc)
    await session.commit()

    mock_planning = types.ModuleType("planner.modules.planning.public")
    mock_planning.get_decided_steps = AsyncMock(
        return_value=[
            {
                "id": uuid.uuid4(),
                "step_no": 1,
                "operation": "expand_nested",
                "parameters": {"column": "line_items", "key_column": "_row", "child_table": "LineItems"},
            }
        ]
    )
    monkeypatch.setitem(sys.modules, "planner.modules.planning.public", mock_planning)

    res = await _async_run_validation(str(plan_id), str(job_id), 1)
    assert res["passed"] is True
    assert res["tests"] == 1

    # Verify TestRunRow entries (before and after)
    runs = (
        await session.execute(
            select(TestRunRow).where(TestRunRow.test_case_id == tc.id)
        )
    ).scalars().all()
    assert len(runs) == 2
    phases = {r.phase for r in runs}
    assert phases == {"before", "after"}
    assert all(r.result == "passed" for r in runs)

    # Verify ReconciliationRow entries
    recs = (
        await session.execute(
            select(ReconciliationRow).where(ReconciliationRow.plan_id == plan_id)
        )
    ).scalars().all()
    by_name = {r.check_name: (r.source_value, r.output_value) for r in recs}
    assert by_name["row_count"] == ("2", "2")
    assert by_name["row_count:LineItems"] == ("2", "2")
    # recomputed from the source JSON, not copied from the child table
    assert by_name["sum:LineItems.amount"] == ("150", "150")
    assert all(r.ok is True for r in recs)

    # Verify OutboxEvent
    events = (
        await session.execute(
            select(OutboxEvent).where(OutboxEvent.event_type == "validation.completed")
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].payload["passed"] is True
