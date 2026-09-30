"""Unit tests for get_validation feature."""

from __future__ import annotations

import sys
import types
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.errors import AppError
from planner.modules.validation.features.get_validation.service import get_validation
from planner.modules.validation.models import ReconciliationRow, TestCaseRow, TestRunRow
from planner.modules.validation.public import latest_validation_passed


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
async def test_get_validation_not_found(test_session: AsyncSession, monkeypatch):
    plan_id = uuid.uuid4()
    mock_exec = types.ModuleType("planner.modules.execution.public")
    mock_exec.get_current_version_no = AsyncMock(return_value=0)
    monkeypatch.setitem(sys.modules, "planner.modules.execution.public", mock_exec)

    with pytest.raises(AppError) as exc_info:
        await get_validation(test_session, plan_id)
    assert exc_info.value.code == "VALIDATION_NOT_FOUND"
    assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_get_validation_and_latest_passed(test_session: AsyncSession, monkeypatch):
    plan_id = uuid.uuid4()
    mock_exec = types.ModuleType("planner.modules.execution.public")
    mock_exec.get_current_version_no = AsyncMock(return_value=1)
    monkeypatch.setitem(sys.modules, "planner.modules.execution.public", mock_exec)

    tc1 = TestCaseRow(
        id=uuid.uuid4(),
        plan_id=plan_id,
        type="unit",
        target_step_id=None,
        name="no_nulls_supplier_name",
        definition={"check": "no_nulls", "column": "supplier_name"},
    )
    tc2 = TestCaseRow(
        id=uuid.uuid4(),
        plan_id=plan_id,
        type="integration",
        target_step_id=None,
        name="row_count_equals",
        definition={"check": "row_count_equals", "expected": 22},
    )
    test_session.add_all([tc1, tc2])
    await test_session.commit()

    # Runs for tc1: before=passed, after=passed
    tr1_b = TestRunRow(
        id=uuid.uuid4(),
        test_case_id=tc1.id,
        version_no=1,
        phase="before",
        result="passed",
        detail="No nulls in before",
    )
    tr1_a = TestRunRow(
        id=uuid.uuid4(),
        test_case_id=tc1.id,
        version_no=1,
        phase="after",
        result="passed",
        detail="No nulls in after",
    )
    # Runs for tc2: before=failed, after=passed
    tr2_b = TestRunRow(
        id=uuid.uuid4(),
        test_case_id=tc2.id,
        version_no=1,
        phase="before",
        result="failed",
        detail="Row count mismatch in before",
    )
    tr2_a = TestRunRow(
        id=uuid.uuid4(),
        test_case_id=tc2.id,
        version_no=1,
        phase="after",
        result="passed",
        detail="Row count matched in after",
    )
    rec1 = ReconciliationRow(
        id=uuid.uuid4(),
        plan_id=plan_id,
        version_no=1,
        check_name="gross_total",
        source_value="154292.0",
        output_value="154292.0",
        ok=True,
    )
    test_session.add_all([tr1_b, tr1_a, tr2_b, tr2_a, rec1])
    await test_session.commit()

    resp = await get_validation(test_session, plan_id)
    assert resp.plan_id == plan_id
    assert resp.version_no == 1
    assert resp.passed is True
    assert len(resp.test_cases) == 2
    assert len(resp.reconciliation) == 1
    assert resp.reconciliation[0].check_name == "gross_total"
    assert resp.reconciliation[0].ok is True

    # Check latest_validation_passed directly
    passed = await latest_validation_passed(test_session, plan_id, 1)
    assert passed is True

    # Now add an after run that failed for tc2
    from datetime import datetime, timedelta, timezone

    tr2_a_fail = TestRunRow(
        id=uuid.uuid4(),
        test_case_id=tc2.id,
        version_no=1,
        phase="after",
        result="failed",
        detail="Unexpected failure",
        run_at=datetime.now(timezone.utc) + timedelta(seconds=5),
    )
    test_session.add(tr2_a_fail)
    await test_session.commit()

    resp2 = await get_validation(test_session, plan_id)
    assert resp2.passed is False

    passed2 = await latest_validation_passed(test_session, plan_id, 1)
    assert passed2 is False
