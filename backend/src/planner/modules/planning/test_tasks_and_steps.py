"""Unit tests for planning task utilities and build_steps_from_rules."""

from __future__ import annotations

import polars as pl
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.engine.infer.rules import InferredRule
from planner.engine.loss.estimator import cumulative_loss, estimate_step_loss
from planner.engine.profile.profiler import ColumnProfile, TableProfile
from planner.modules.planning.models import LossEstimateRow, Plan, PlanStep
from planner.modules.planning.public import (
    get_decided_steps,
    get_plan_row,
    get_plan_steps_with_loss,
)
from planner.modules.planning.tasks import build_steps_from_rules


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


def test_build_steps_from_rules_ordering_and_mapping():
    # Construct a dataframe with realistic columns and duplicates
    df = pl.DataFrame(
        {
            "id": ["INV-001", "INV-002", "INV-002"],
            "all_null_col": [None, None, None],
            "price_str": ["$10.50", "$20.00", "$20.00"],
            "vendor": ["Acme Corp", "Acme", "Acme"],
            "inv_date": ["2026-01-01", "2026-01-02", "2026-01-02"],
            "target_fill": [None, "filled", "filled"],
            "source_fill": ["const", "const", "const"],
            "items": ['[{"sku":"1"}]', '[{"sku":"2"}]', '[{"sku":"2"}]'],
            "subtotal": [10.5, 20.0, 20.0],
            "total_redundant": [10.5, 20.0, 20.0],
        }
    )

    profile = TableProfile(
        table_name="test_table",
        row_count=3,
        column_count=10,
        columns=[
            ColumnProfile("id", 0, "String", "identifier", 0, 0.0, 2, "INV-001", "INV-002", None, []),
            ColumnProfile("all_null_col", 1, "String", "unknown", 3, 1.0, 0, None, None, None, ["all_null"]),
            ColumnProfile("price_str", 2, "String", "numeric_text", 0, 0.0, 2, "$10.50", "$20.00", None, ["numeric_as_text"]),
            ColumnProfile("vendor", 3, "String", "category", 0, 0.0, 2, "Acme", "Acme Corp", None, []),
            ColumnProfile("inv_date", 4, "String", "date", 0, 0.0, 2, "2026-01-01", "2026-01-02", None, []),
            ColumnProfile("target_fill", 5, "String", "category", 1, 0.33, 1, "filled", "filled", None, []),
            ColumnProfile("source_fill", 6, "String", "category", 0, 0.0, 1, "const", "const", None, []),
            ColumnProfile("items", 7, "String", "nested_json", 0, 0.0, 2, None, None, None, ["nested_json"]),
            ColumnProfile("subtotal", 8, "Float64", "float", 0, 0.0, 2, "10.5", "20.0", 15.25, []),
            ColumnProfile("total_redundant", 9, "Float64", "float", 0, 0.0, 2, "10.5", "20.0", 15.25, []),
        ],
        issues=["all-null-columns", "numeric-as-text-columns"],
    )

    rules = [
        InferredRule("primary_key", ["id"], {"column": "id"}, 1.0),
        InferredRule(
            "entity_group",
            ["vendor"],
            {"column": "vendor", "groups": [{"canonical": "Acme", "variants": ["Acme Corp", "Acme"]}]},
            0.9,
        ),
        InferredRule(
            "cross_field_fill",
            ["target_fill", "source_fill"],
            {"target": "target_fill", "source": "source_fill", "value": "filled"},
            0.85,
        ),
        InferredRule(
            "one_to_many",
            ["items"],
            {"parent_key": "id", "child_table": "LineItems"},
            0.95,
        ),
        InferredRule(
            "arithmetic",
            ["total_redundant", "subtotal"],
            {"target": "total_redundant", "formula": "subtotal", "kind": "equality"},
            1.0,
        ),
    ]

    steps = build_steps_from_rules(rules, profile, df)
    ops = [s.operation for s in steps]

    # Verify canonical order:
    # drop_column (all-null) -> cast_type -> replace_value -> standardise_format -> fill_missing -> expand_nested -> deduplicate -> drop_column (arithmetic)
    expected_order = [
        "drop_column",
        "cast_type",
        "replace_value",
        "standardise_format",
        "fill_missing",
        "expand_nested",
        "deduplicate",
        "drop_column",
    ]
    assert ops == expected_order

    # Check drop_null params
    assert steps[0].parameters == {"column": "all_null_col"}
    # Check cast_type params
    assert steps[1].parameters == {"column": "price_str", "dtype": "float", "strip_chars": "$, "}
    # Check replace_value params
    assert steps[2].parameters == {"column": "vendor", "mapping": {"Acme Corp": "Acme"}}
    # Check standardise_format params
    assert steps[3].parameters == {"column": "inv_date", "format": "iso_date"}
    # Check fill_missing params
    assert steps[4].parameters == {"column": "target_fill", "value": "filled"}
    # Check expand_nested params
    assert steps[5].parameters == {"column": "items", "key_column": "id", "child_table": "LineItems"}
    # Check deduplicate params
    assert steps[6].parameters == {"subset": None}
    # Check arithmetic redundant drop params
    assert steps[7].parameters == {"column": "total_redundant", "redundant_with": "subtotal"}

    # Compute loss for each step
    losses = [estimate_step_loss(df, s.operation, s.parameters) for s in steps]
    assert len(losses) == len(steps)
    cum = cumulative_loss(losses)
    assert 0.0 <= cum <= 1.0


@pytest.mark.asyncio
async def test_planning_public_helpers(test_session: AsyncSession):
    import uuid

    dataset_id = uuid.uuid4()
    plan = Plan(dataset_id=dataset_id, status="proposed")
    test_session.add(plan)
    await test_session.flush()

    step1 = PlanStep(
        plan_id=plan.id,
        step_no=1,
        operation="drop_column",
        parameters={"column": "c1"},
        rationale="r1",
        confidence=1.0,
        decision="accepted",
    )
    step2 = PlanStep(
        plan_id=plan.id,
        step_no=2,
        operation="cast_type",
        parameters={"column": "c2", "dtype": "float"},
        rationale="r2",
        confidence=0.9,
        decision="edited",
    )
    step3 = PlanStep(
        plan_id=plan.id,
        step_no=3,
        operation="deduplicate",
        parameters={"subset": None},
        rationale="r3",
        confidence=0.8,
        decision="pending",
    )
    test_session.add_all([step1, step2, step3])
    await test_session.flush()

    loss1 = LossEstimateRow(
        step_id=step1.id,
        rows_affected=5,
        columns_affected=1,
        cells_affected=5,
        estimated_loss=0.01,
    )
    test_session.add(loss1)
    await test_session.commit()

    # Test get_plan_row
    loaded_plan = await get_plan_row(test_session, plan.id)
    assert loaded_plan is not None
    assert loaded_plan.id == plan.id

    # Test get_decided_steps
    decided = await get_decided_steps(test_session, plan.id)
    assert len(decided) == 2
    assert decided[0]["step_no"] == 1
    assert decided[0]["operation"] == "drop_column"
    assert decided[1]["step_no"] == 2
    assert decided[1]["operation"] == "cast_type"

    # Test get_plan_steps_with_loss
    steps_with_loss = await get_plan_steps_with_loss(test_session, plan.id)
    assert len(steps_with_loss) == 3
    s1, l1 = steps_with_loss[0]
    assert s1.step_no == 1
    assert l1 is not None
    assert l1.cells_affected == 5
    s3, l3 = steps_with_loss[2]
    assert s3.step_no == 3
    assert l3 is None
