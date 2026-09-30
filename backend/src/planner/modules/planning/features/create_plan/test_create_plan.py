"""Unit tests for create_plan feature."""

from __future__ import annotations

from unittest.mock import patch
import uuid
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.modules.planning.features.create_plan.schemas import CreatePlanRequest
from planner.modules.planning.features.create_plan.service import create_plan


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
async def test_create_plan_success(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    req = CreatePlanRequest(loss_threshold=0.08)

    with patch("planner.worker.celery_app.send_task") as mock_send_task:
        plan_out = await create_plan(test_session, dataset_id, req)
        assert plan_out.dataset_id == dataset_id
        assert plan_out.status == "proposed"
        assert plan_out.loss_threshold == 0.08
        assert plan_out.steps == []

        mock_send_task.assert_called_once()
        args, kwargs = mock_send_task.call_args
        assert args[0] == "planner.generate_plan"
        assert kwargs["queue"] == "plan"

    dumped = plan_out.model_dump(by_alias=True)
    assert "datasetId" in dumped
    assert "lossThreshold" in dumped
    assert "totalEstimatedLoss" in dumped
