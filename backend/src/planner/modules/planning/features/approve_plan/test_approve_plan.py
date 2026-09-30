"""Unit tests for approve_plan feature."""

from __future__ import annotations

from unittest.mock import patch
import uuid
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.errors import AppError
from planner.modules.planning.features.approve_plan.service import approve_plan
from planner.modules.planning.models import Plan, PlanStep


@pytest.fixture
async def test_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        execution_options={
            "schema_translate_map": {
                "profiling": None,
                "planning": None,
                "execution": None,
                "validation": None,
                "datasets": None,
                "users": None,
                "audit": None,
                "model_config": None,
                "evaluation": None,
            }
        },
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_approve_plan_success(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    plan = Plan(dataset_id=dataset_id, status="proposed")
    test_session.add(plan)
    await test_session.flush()

    step1 = PlanStep(
        plan_id=plan.id,
        step_no=1,
        operation="drop_column",
        parameters={"column": "c1"},
        rationale="null",
        confidence=1.0,
        decision="accepted",
    )
    step2 = PlanStep(
        plan_id=plan.id,
        step_no=2,
        operation="replace_value",
        parameters={"column": "c2", "mapping": {"a": "b"}},
        rationale="clean",
        confidence=0.9,
        decision="rejected",
    )
    test_session.add_all([step1, step2])
    await test_session.commit()

    with patch("planner.worker.celery_app.send_task") as mock_send_task:
        res = await approve_plan(test_session, plan.id)
        assert res.plan_id == plan.id
        assert res.status == "approved"
        assert res.job_id is not None

        mock_send_task.assert_called_once()
        args, kwargs = mock_send_task.call_args
        assert args[0] == "planner.generate_tests"
        assert kwargs["queue"] == "validate"

    dumped = res.model_dump(by_alias=True)
    assert "planId" in dumped
    assert "status" in dumped
    assert "jobId" in dumped


@pytest.mark.asyncio
async def test_approve_plan_not_fully_decided(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    plan = Plan(dataset_id=dataset_id, status="proposed")
    test_session.add(plan)
    await test_session.flush()

    step1 = PlanStep(
        plan_id=plan.id,
        step_no=1,
        operation="drop_column",
        parameters={"column": "c1"},
        rationale="null",
        confidence=1.0,
        decision="pending",
    )
    test_session.add(step1)
    await test_session.commit()

    with pytest.raises(AppError) as exc_info:
        await approve_plan(test_session, plan.id)
    assert exc_info.value.code == "PLAN_NOT_FULLY_DECIDED"
    assert exc_info.value.status == 409


@pytest.mark.asyncio
async def test_approve_plan_not_decidable(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    plan = Plan(dataset_id=dataset_id, status="approved")
    test_session.add(plan)
    await test_session.commit()

    with pytest.raises(AppError) as exc_info:
        await approve_plan(test_session, plan.id)
    assert exc_info.value.code == "PLAN_NOT_DECIDABLE"
    assert exc_info.value.status == 409
