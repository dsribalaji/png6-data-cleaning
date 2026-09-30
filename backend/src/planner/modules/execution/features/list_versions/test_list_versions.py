"""Unit tests for list_versions feature."""

from __future__ import annotations

import sys
import types
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.errors import AppError
from planner.modules.execution.features.list_versions.service import list_versions
from planner.modules.execution.models import PipelineVersion


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
async def test_list_versions_plan_not_found(test_session: AsyncSession, monkeypatch):
    plan_id = uuid.uuid4()
    mock_planning = types.ModuleType("planner.modules.planning.public")
    mock_get_plan_row = AsyncMock(return_value=None)
    mock_planning.get_plan_row = mock_get_plan_row
    monkeypatch.setitem(sys.modules, "planner.modules.planning.public", mock_planning)

    with pytest.raises(AppError) as exc_info:
        await list_versions(test_session, plan_id)
    assert exc_info.value.code == "PLAN_NOT_FOUND"
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_list_versions_success(test_session: AsyncSession, monkeypatch):
    plan_id = uuid.uuid4()
    mock_plan = types.SimpleNamespace(id=plan_id, dataset_id=uuid.uuid4(), status="approved")
    mock_planning = types.ModuleType("planner.modules.planning.public")
    mock_planning.get_plan_row = AsyncMock(return_value=mock_plan)
    monkeypatch.setitem(sys.modules, "planner.modules.planning.public", mock_planning)

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
    v2 = PipelineVersion(
        id=uuid.uuid4(),
        plan_id=plan_id,
        version_no=2,
        step_id=uuid.uuid4(),
        snapshot_object_key=f"snapshots/{plan_id}/v2.parquet",
        inverse_operation={"op": "restore_nulls"},
    )
    test_session.add_all([v1, v0, v2])
    await test_session.commit()

    resp = await list_versions(test_session, plan_id)
    assert resp.plan_id == plan_id
    assert resp.total == 3
    assert len(resp.items) == 3
    assert [item.version_no for item in resp.items] == [0, 1, 2]
    assert resp.items[0].is_current is False
    assert resp.items[1].is_current is False
    assert resp.items[2].is_current is True
