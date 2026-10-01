"""Unit tests for get_rules feature."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.errors import AppError
from planner.modules.profiling.features.get_rules.service import get_rules
from planner.modules.profiling.models import InferredRuleRow


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
async def test_get_rules_success(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    rule1 = InferredRuleRow(
        dataset_id=dataset_id,
        rule_type="primary_key",
        columns=["invoice_number"],
        expression={"column": "invoice_number"},
        confidence=1.0,
        evidence_rows={"distinct_count": 22},
        source="deterministic",
    )
    rule2 = InferredRuleRow(
        dataset_id=dataset_id,
        rule_type="entity_group",
        columns=["supplier_name"],
        expression={"column": "supplier_name", "groups": []},
        confidence=0.85,
        evidence_rows={},
        source="deterministic",
    )
    test_session.add_all([rule1, rule2])
    await test_session.commit()

    resp = await get_rules(test_session, dataset_id)
    assert resp.dataset_id == dataset_id
    assert resp.total == 2
    assert len(resp.items) == 2
    # Verify ordered by confidence desc
    assert resp.items[0].confidence >= resp.items[1].confidence
    assert resp.items[0].rule_type == "primary_key"

    # Verify camelCase serialization
    dumped = resp.model_dump(by_alias=True)
    assert "datasetId" in dumped
    assert "items" in dumped
    assert "ruleType" in dumped["items"][0]


@pytest.mark.asyncio
async def test_get_rules_not_found(test_session: AsyncSession):
    missing_id = uuid.uuid4()
    with pytest.raises(AppError) as exc_info:
        await get_rules(test_session, missing_id)
    assert exc_info.value.code == "RULES_NOT_FOUND"
    assert exc_info.value.status == 404
