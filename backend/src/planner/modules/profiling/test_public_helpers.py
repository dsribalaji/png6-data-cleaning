"""Unit tests for profiling public interface helpers."""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.modules.profiling.models import ColumnProfileRow, InferredRuleRow, ProfileRun
from planner.modules.profiling.public import (
    get_column_profile_rows,
    get_profile_run,
    list_rule_rows,
)


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
async def test_profiling_public_helpers(test_session: AsyncSession):
    dataset_id = uuid.uuid4()
    run = ProfileRun(
        dataset_id=dataset_id,
        row_count=50,
        column_count=2,
        issues=["numeric-as-text"],
    )
    col1 = ColumnProfileRow(
        dataset_id=dataset_id,
        column_name="c1",
        ordinal=0,
        physical_type="String",
        semantic_type="identifier",
        null_count=0,
        null_pct=0.0,
        distinct_count=50,
        flags=[],
    )
    col2 = ColumnProfileRow(
        dataset_id=dataset_id,
        column_name="c2",
        ordinal=1,
        physical_type="String",
        semantic_type="date",
        null_count=0,
        null_pct=0.0,
        distinct_count=20,
        flags=[],
    )
    rule1 = InferredRuleRow(
        dataset_id=dataset_id,
        rule_type="primary_key",
        columns=["c1"],
        expression={"column": "c1"},
        confidence=1.0,
        source="deterministic",
    )
    rule2 = InferredRuleRow(
        dataset_id=dataset_id,
        rule_type="semantic_type",
        columns=["c2"],
        expression={"column": "c2", "semantic_type": "date"},
        confidence=0.9,
        source="deterministic",
    )
    test_session.add_all([run, col1, col2, rule1, rule2])
    await test_session.commit()

    run_row = await get_profile_run(test_session, dataset_id)
    assert run_row is not None
    assert run_row.row_count == 50

    col_rows = await get_column_profile_rows(test_session, dataset_id)
    assert len(col_rows) == 2
    assert col_rows[0].column_name == "c1"
    assert col_rows[1].column_name == "c2"

    rules = await list_rule_rows(test_session, dataset_id)
    assert len(rules) == 2
    assert rules[0].confidence >= rules[1].confidence
