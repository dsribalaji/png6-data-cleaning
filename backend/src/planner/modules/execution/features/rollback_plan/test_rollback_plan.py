"""Unit tests for rollback_plan feature."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.errors import AppError
from planner.modules.execution.features.rollback_plan.service import rollback_request
from planner.modules.execution.models import PipelineVersion, RollbackRow
from planner.modules.execution.schemas import RollbackRequest


@pytest.fixture
async def test_session():
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
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_rollback_reason_too_short(test_session: AsyncSession):
    plan_id = uuid.uuid4()
    req = RollbackRequest(to_version=1, reason="too short")
    with pytest.raises(AppError) as exc_info:
        await rollback_request(test_session, plan_id, req)
    assert exc_info.value.code == "REASON_REQUIRED"
    assert exc_info.value.status == 400


@pytest.mark.asyncio
async def test_rollback_plan_not_found(test_session: AsyncSession):
    plan_id = uuid.uuid4()
    req = RollbackRequest(to_version=1, reason="A valid reason with >= 10 characters")
    with pytest.raises(AppError) as exc_info:
        await rollback_request(test_session, plan_id, req)
    assert exc_info.value.code == "PLAN_NOT_FOUND"
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_rollback_version_not_found(test_session: AsyncSession):
    plan_id = uuid.uuid4()
    v0 = PipelineVersion(
        id=uuid.uuid4(),
        plan_id=plan_id,
        version_no=0,
        step_id=None,
        snapshot_object_key=f"snapshots/{plan_id}/v0.parquet",
        inverse_operation={"op": "v0_original"},
    )
    test_session.add(v0)
    await test_session.commit()

    req = RollbackRequest(to_version=5, reason="A valid reason with >= 10 characters")
    with pytest.raises(AppError) as exc_info:
        await rollback_request(test_session, plan_id, req)
    assert exc_info.value.code == "VERSION_NOT_FOUND"
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_rollback_success(test_session: AsyncSession):
    plan_id = uuid.uuid4()
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
    test_session.add_all([v0, v1])
    await test_session.commit()

    req = RollbackRequest(to_version=0, reason="Reverting step 1 due to bad logic")

    with patch("planner.worker.celery_app.send_task") as mock_send_task:
        resp = await rollback_request(test_session, plan_id, req)

        assert resp.plan_id == plan_id
        assert resp.from_version == 1
        assert resp.to_version == 0
        assert resp.job_id is not None

        mock_send_task.assert_called_once_with(
            "planner.rollback_plan",
            args=[str(plan_id), str(resp.job_id), 0, "Reverting step 1 due to bad logic"],
            queue="execute",
        )

        rows = (
            await test_session.execute(
                select(RollbackRow).where(RollbackRow.plan_id == plan_id)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].from_version_no == 1
        assert rows[0].to_version_no == 0
        assert rows[0].reason == "Reverting step 1 due to bad logic"
        assert rows[0].completed_at is None
