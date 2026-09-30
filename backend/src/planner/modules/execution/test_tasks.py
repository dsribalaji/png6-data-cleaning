"""Tests for execution module celery tasks."""

from __future__ import annotations

import io
import sys
import types
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import polars as pl
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.outbox import OutboxEvent
from planner.modules.execution.models import PipelineVersion, RollbackRow
from planner.modules.execution.tasks import _async_execute_plan, _async_rollback_plan


@pytest.fixture
async def setup_db(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path))
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    from sqlalchemy import Column, Table, Uuid

    if (
        "planning.plan_steps" not in Base.metadata.tables
        and "plan_steps" not in Base.metadata.tables
    ):
        Table(
            "plan_steps",
            Base.metadata,
            Column("id", Uuid, primary_key=True),
            schema="planning",
        )

    for table in Base.metadata.tables.values():
        table.schema = None

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Monkeypatch SessionLocal in tasks
    monkeypatch.setattr("planner.modules.execution.tasks.SessionLocal", session_factory)

    async with session_factory() as session:
        yield session, tmp_path

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_execute_plan_not_approved(setup_db, monkeypatch):
    session, _ = setup_db
    plan_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_plan = types.SimpleNamespace(id=plan_id, dataset_id=uuid.uuid4(), status="draft")
    mock_planning = types.ModuleType("planner.modules.planning.public")
    mock_planning.get_plan_row = AsyncMock(return_value=mock_plan)
    mock_planning.get_decided_steps = AsyncMock(return_value=[])
    monkeypatch.setitem(sys.modules, "planner.modules.planning.public", mock_planning)

    with pytest.raises(RuntimeError) as exc_info:
        await _async_execute_plan(str(plan_id), str(job_id))
    assert "PLAN_NOT_APPROVED" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execute_plan_success_and_idempotency(setup_db, monkeypatch):
    session, tmp_path = setup_db
    plan_id = uuid.uuid4()
    job_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    # Create dummy base parquet in storage
    df = pl.DataFrame({"supplier": ["Acme Corp", "Beta LLC"], "amount": [100.0, 200.0]})
    buf = io.BytesIO()
    df.write_parquet(buf)
    raw_bytes = buf.getvalue()

    ingested_key = f"datasets/{dataset_id}/raw.parquet"
    ingested_path = tmp_path / ingested_key
    ingested_path.parent.mkdir(parents=True, exist_ok=True)
    ingested_path.write_bytes(raw_bytes)

    # Mock datasets.public
    mock_ds = types.ModuleType("planner.modules.datasets.public")
    mock_ds.get_dataset = AsyncMock(
        return_value=types.SimpleNamespace(id=dataset_id, ingested_object_key=ingested_key)
    )
    monkeypatch.setitem(sys.modules, "planner.modules.datasets.public", mock_ds)

    # Mock planning.public
    step_id = uuid.uuid4()
    mock_plan = types.SimpleNamespace(id=plan_id, dataset_id=dataset_id, status="approved")
    steps = [
        {
            "id": step_id,
            "step_no": 1,
            "operation": "replace_value",
            "parameters": {"column": "supplier", "mapping": {"Beta LLC": "Beta Corp"}},
        }
    ]
    mock_planning = types.ModuleType("planner.modules.planning.public")
    mock_planning.get_plan_row = AsyncMock(return_value=mock_plan)
    mock_planning.get_decided_steps = AsyncMock(return_value=steps)
    monkeypatch.setitem(sys.modules, "planner.modules.planning.public", mock_planning)

    with patch("planner.worker.celery_app.send_task") as mock_send_task:
        res = await _async_execute_plan(str(plan_id), str(job_id))
        assert res["plan_id"] == str(plan_id)
        assert res["versions"] == 1

        mock_send_task.assert_called_once_with(
            "planner.run_validation",
            args=[str(plan_id), str(job_id), 1],
            queue="validate",
        )

    # Verify versions inserted: v0 and v1
    v_rows = (
        await session.execute(
            select(PipelineVersion)
            .where(PipelineVersion.plan_id == plan_id)
            .order_by(PipelineVersion.version_no.asc())
        )
    ).scalars().all()
    assert len(v_rows) == 2
    assert v_rows[0].version_no == 0
    assert v_rows[0].inverse_operation == {"op": "v0_original"}
    assert v_rows[1].version_no == 1

    # Verify outbox events
    events = (await session.execute(select(OutboxEvent))).scalars().all()
    event_types = [e.event_type for e in events]
    assert "plan.step_executed" in event_types
    assert "plan.executed" in event_types

    # Idempotency check: running again should return already_done
    res_idempotent = await _async_execute_plan(str(plan_id), str(job_id))
    assert res_idempotent["status"] == "already_done"


@pytest.mark.asyncio
async def test_rollback_plan_task(setup_db, monkeypatch):
    session, tmp_path = setup_db
    plan_id = uuid.uuid4()
    job_id = uuid.uuid4()

    # Setup snapshots v0, v1
    v0_df = pl.DataFrame({"a": [1, 2]})
    v0_path = tmp_path / "snapshots" / str(plan_id) / "v0.parquet"
    v0_path.parent.mkdir(parents=True, exist_ok=True)
    v0_df.write_parquet(v0_path)

    v1_df = pl.DataFrame({"a": [1, 20]})
    v1_path = tmp_path / "snapshots" / str(plan_id) / "v1.parquet"
    v1_df.write_parquet(v1_path)

    v0 = PipelineVersion(
        id=uuid.uuid4(),
        plan_id=plan_id,
        version_no=0,
        step_id=None,
        snapshot_object_key=f"snapshots/{plan_id}/v0.parquet",
        inverse_operation={"op": "v0_original"},
    )
    v1 = PipelineVersion(
        id=uuid.uuid4(),
        plan_id=plan_id,
        version_no=1,
        step_id=uuid.uuid4(),
        snapshot_object_key=f"snapshots/{plan_id}/v1.parquet",
        inverse_operation={"op": "restore_cells"},
    )
    rb_row = RollbackRow(
        id=uuid.uuid4(),
        plan_id=plan_id,
        from_version_no=1,
        to_version_no=0,
        reason="Mistake in step 1",
    )
    session.add_all([v0, v1, rb_row])
    await session.commit()

    res = await _async_rollback_plan(str(plan_id), str(job_id), 0, "Mistake in step 1")
    assert res["from_version"] == 1
    assert res["to_version"] == 0
    assert res["new_version"] == 2

    # Check that new PipelineVersion v2 was created
    v2_row = (
        await session.execute(
            select(PipelineVersion).where(
                PipelineVersion.plan_id == plan_id, PipelineVersion.version_no == 2
            )
        )
    ).scalar_one()
    assert v2_row.snapshot_object_key == f"snapshots/{plan_id}/v2.parquet"
    assert v2_row.inverse_operation["op"] == "rollback"

    # Verify byte-identical restore
    v2_bytes = (tmp_path / f"snapshots/{plan_id}/v2.parquet").read_bytes()
    v0_bytes = v0_path.read_bytes()
    assert v2_bytes == v0_bytes

    # Check RollbackRow completed_at updated
    updated_rb = (
        await session.execute(select(RollbackRow).where(RollbackRow.id == rb_row.id))
    ).scalar_one()
    assert updated_rb.completed_at is not None
