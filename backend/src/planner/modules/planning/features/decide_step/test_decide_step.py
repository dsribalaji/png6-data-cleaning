"""Unit tests for decide_step feature."""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.errors import AppError
from planner.modules.planning.features.decide_step.schemas import DecideStepRequest
from planner.modules.planning.features.decide_step.service import decide_step
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
async def test_decide_step_accept(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    plan = Plan(dataset_id=dataset_id, status="proposed")
    test_session.add(plan)
    await test_session.flush()

    step = PlanStep(
        plan_id=plan.id,
        step_no=1,
        operation="drop_column",
        parameters={"column": "unneeded_col"},
        rationale="100% null",
        confidence=1.0,
        decision="pending",
    )
    test_session.add(step)
    await test_session.flush()

    loss = LossEstimateRow(
        step_id=step.id,
        rows_affected=10,
        columns_affected=1,
        cells_affected=10,
        estimated_loss=0.01,
    )
    test_session.add(loss)
    await test_session.commit()

    req = DecideStepRequest(decision="accepted")
    res = await decide_step(test_session, plan.id, step.id, req)
    assert res.decision == "accepted"
    assert res.estimated_loss is not None
    assert res.estimated_loss.estimated_loss == 0.01


@pytest.mark.asyncio
async def test_decide_step_edit(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    plan = Plan(dataset_id=dataset_id, status="proposed")
    test_session.add(plan)
    await test_session.flush()

    step = PlanStep(
        plan_id=plan.id,
        step_no=1,
        operation="replace_value",
        parameters={"column": "supplier", "mapping": {"ACME INC": "Acme"}},
        rationale="Standardise supplier",
        confidence=0.9,
        decision="pending",
    )
    test_session.add(step)
    await test_session.commit()

    # Valid edit
    req = DecideStepRequest(
        decision="edited",
        parameters={"column": "supplier", "mapping": {"ACME INC": "Acme Corp"}},
        reason="Updated to canonical legal entity",
    )
    res = await decide_step(test_session, plan.id, step.id, req)
    assert res.decision == "edited"
    assert res.decision_reason == "Updated to canonical legal entity"
    assert res.parameters["mapping"]["ACME INC"] == "Corp".join(["Acme ", ""])


@pytest.mark.asyncio
async def test_decide_step_edit_invalid_params(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    plan = Plan(dataset_id=dataset_id, status="proposed")
    test_session.add(plan)
    await test_session.flush()

    step = PlanStep(
        plan_id=plan.id,
        step_no=1,
        operation="replace_value",
        parameters={"column": "supplier", "mapping": {"ACME INC": "Acme"}},
        rationale="Standardise supplier",
        confidence=0.9,
        decision="pending",
    )
    test_session.add(step)
    await test_session.commit()

    # Invalid edit (mapping is not a dict)
    req = DecideStepRequest(
        decision="edited",
        parameters={"column": "supplier", "mapping": "invalid"},
    )
    with pytest.raises(AppError) as exc_info:
        await decide_step(test_session, plan.id, step.id, req)
    assert exc_info.value.code == "INVALID_PARAMETERS"
    assert exc_info.value.status == 400


@pytest.mark.asyncio
async def test_decide_step_invalid_decision(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    plan = Plan(dataset_id=dataset_id, status="proposed")
    test_session.add(plan)
    await test_session.flush()

    step = PlanStep(
        plan_id=plan.id,
        step_no=1,
        operation="drop_column",
        parameters={"column": "col"},
        rationale="test",
        confidence=1.0,
    )
    test_session.add(step)
    await test_session.commit()

    req = DecideStepRequest(decision="invalid_choice")
    with pytest.raises(AppError) as exc_info:
        await decide_step(test_session, plan.id, step.id, req)
    assert exc_info.value.code == "INVALID_DECISION"
    assert exc_info.value.status == 400


@pytest.mark.asyncio
async def test_decide_step_plan_not_decidable(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    plan = Plan(dataset_id=dataset_id, status="approved")
    test_session.add(plan)
    await test_session.flush()

    step = PlanStep(
        plan_id=plan.id,
        step_no=1,
        operation="drop_column",
        parameters={"column": "col"},
        rationale="test",
        confidence=1.0,
    )
    test_session.add(step)
    await test_session.commit()

    req = DecideStepRequest(decision="accepted")
    with pytest.raises(AppError) as exc_info:
        await decide_step(test_session, plan.id, step.id, req)
    assert exc_info.value.code == "PLAN_NOT_DECIDABLE"
    assert exc_info.value.status == 409
