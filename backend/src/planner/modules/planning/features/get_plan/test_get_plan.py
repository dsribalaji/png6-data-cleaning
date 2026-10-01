"""Unit tests for get_plan feature."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.errors import AppError
from planner.modules.planning.features.get_plan.service import get_plan
from planner.modules.planning.models import LossEstimateRow, Plan, PlanStep


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
async def test_get_plan_success(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    plan = Plan(
        dataset_id=dataset_id,
        status="proposed",
        total_estimated_loss=0.015,
        loss_threshold=0.05,
    )
    test_session.add(plan)
    await test_session.flush()

    step = PlanStep(
        plan_id=plan.id,
        step_no=1,
        operation="drop_column",
        parameters={"column": "customer_vat_number"},
        rationale="100% null column",
        confidence=1.0,
        decision="pending",
    )
    test_session.add(step)
    await test_session.flush()

    loss = LossEstimateRow(
        step_id=step.id,
        rows_affected=22,
        columns_affected=1,
        cells_affected=22,
        estimated_loss=0.015,
    )
    test_session.add(loss)
    await test_session.commit()

    resp = await get_plan(test_session, plan.id)
    assert resp.id == plan.id
    assert resp.dataset_id == dataset_id
    assert resp.status == "proposed"
    assert len(resp.steps) == 1
    assert resp.steps[0].operation == "drop_column"
    assert resp.steps[0].estimated_loss is not None
    assert resp.steps[0].estimated_loss.cells_affected == 22

    dumped = resp.model_dump(by_alias=True)
    assert "datasetId" in dumped
    assert "totalEstimatedLoss" in dumped
    assert "stepNo" in dumped["steps"][0]
    assert "rowsAffected" in dumped["steps"][0]["estimatedLoss"]


@pytest.mark.asyncio
async def test_get_plan_not_found(test_session: AsyncSession):
    missing_id = uuid.uuid4()
    with pytest.raises(AppError) as exc_info:
        await get_plan(test_session, missing_id)
    assert exc_info.value.code == "PLAN_NOT_FOUND"
    assert exc_info.value.status == 404
