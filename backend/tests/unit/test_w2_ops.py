"""Unit and property tests for engine operations, loss estimation, and test generation.

Pure data logic verification.
"""

from __future__ import annotations

import json
from pathlib import Path
from hypothesis import given, settings
from hypothesis import strategies as st
import polars as pl
import pytest

from planner.engine.loss import (
    DEFAULT_LOSS_THRESHOLD,
    check_threshold,
    cumulative_loss,
    estimate_step_loss,
)
from planner.engine.ops import (
    OPS,
    LossEstimate,
    apply_inverse,
    frame_equal,
)
from planner.engine.profile.profiler import ColumnProfile, TableProfile
from planner.engine.tests_gen import (
    SUPPORTED_CHECKS,
    TestCase,
    export_pytest,
    generate_checks,
    run_checks,
)


# =====================================================================
# (a) Hand-built apply/inverse round-trip for EACH of the 8 ops
# =====================================================================


def test_roundtrip_replace_value() -> None:
    op = OPS["replace_value"]
    before = pl.DataFrame({"status": ["active", "pending", "active", "inactive"]})
    schema = {"status": "String"}
    params = {"column": "status", "mapping": {"pending": "active"}}

    op.validate(params, schema)
    after = op.apply(before, params)
    inv = op.inverse(before, after, params)
    restored = apply_inverse(after, inv)

    assert frame_equal(restored, before)


def test_roundtrip_fill_missing() -> None:
    op = OPS["fill_missing"]
    before = pl.DataFrame({"amount": [10.0, None, 25.5, None]})
    schema = {"amount": "Float64"}
    params = {"column": "amount", "value": 0.0}

    op.validate(params, schema)
    after = op.apply(before, params)
    inv = op.inverse(before, after, params)
    restored = apply_inverse(after, inv)

    assert frame_equal(restored, before)


def test_roundtrip_drop_column() -> None:
    op = OPS["drop_column"]
    before = pl.DataFrame({"a": [1, 2], "b": ["x", "y"], "c": [3.0, 4.0]})
    schema = {"a": "Int64", "b": "String", "c": "Float64"}
    params = {"column": "b"}

    op.validate(params, schema)
    after = op.apply(before, params)
    inv = op.inverse(before, after, params)
    restored = apply_inverse(after, inv)

    assert frame_equal(restored, before)


def test_roundtrip_cast_type() -> None:
    op = OPS["cast_type"]
    before = pl.DataFrame({"val": ["$10", "$20", "$30"]})
    schema = {"val": "String"}
    params = {"column": "val", "dtype": "int", "strip_chars": "$"}

    op.validate(params, schema)
    after = op.apply(before, params)
    inv = op.inverse(before, after, params)
    restored = apply_inverse(after, inv)

    assert frame_equal(restored, before)


def test_roundtrip_deduplicate() -> None:
    op = OPS["deduplicate"]
    before = pl.DataFrame({
        "id": [1, 2, 2, 3, 1],
        "name": ["A", "B", "B", "C", "A"],
    })
    schema = {"id": "Int64", "name": "String"}
    params = {"subset": ["id", "name"]}

    op.validate(params, schema)
    after = op.apply(before, params)
    inv = op.inverse(before, after, params)
    restored = apply_inverse(after, inv)

    assert frame_equal(restored, before)


def test_roundtrip_derive_column() -> None:
    op = OPS["derive_column"]
    before = pl.DataFrame({"qty": [2.0, 4.0], "unit_price": [10.0, 15.0]})
    schema = {"qty": "Float64", "unit_price": "Float64"}
    params = {
        "name": "total",
        "expression": {
            "op": "multiply",
            "args": [{"column": "qty"}, {"column": "unit_price"}],
        },
    }

    op.validate(params, schema)
    after = op.apply(before, params)
    inv = op.inverse(before, after, params)
    restored = apply_inverse(after, inv)

    assert frame_equal(restored, before)


def test_roundtrip_expand_nested() -> None:
    op = OPS["expand_nested"]
    before = pl.DataFrame({
        "order_id": [1, 2],
        "lines": [
            json.dumps([{"item": "A", "price": 10}, {"item": "B", "price": 20}]),
            json.dumps([{"item": "C", "price": 30}]),
        ],
    })
    schema = {"order_id": "Int64", "lines": "String"}
    params = {"column": "lines", "key_column": "order_id", "child_table": "order_lines"}

    op.validate(params, schema)
    after = op.apply(before, params)
    inv = op.inverse(before, after, params)
    restored = apply_inverse(after, inv)

    assert frame_equal(restored, before)

    tables = op.extract_tables(before, params)
    assert "order_lines" in tables
    child_df = tables["order_lines"]
    assert child_df.height == 3
    assert set(child_df.columns) == {"order_id", "item", "price"}


def test_roundtrip_standardise_format() -> None:
    op = OPS["standardise_format"]
    before = pl.DataFrame({"code": [" ABC ", "DeF", " ghI "]})
    schema = {"code": "String"}
    params = {"column": "code", "format": "upper"}

    op.validate(params, schema)
    after = op.apply(before, params)
    inv = op.inverse(before, after, params)
    restored = apply_inverse(after, inv)

    assert frame_equal(restored, before)


# =====================================================================
# (b) Hypothesis property tests per op (max_examples=25, deadline=None)
# =====================================================================


@settings(max_examples=25, deadline=None)
@given(st.lists(st.sampled_from(["alpha", "beta", "gamma", "delta"]), min_size=1, max_size=20))
def test_prop_replace_value(values: list[str]) -> None:
    op = OPS["replace_value"]
    df = pl.DataFrame({"col": values})
    params = {"column": "col", "mapping": {"alpha": "omega", "beta": "theta"}}
    after = op.apply(df, params)
    inv = op.inverse(df, after, params)
    restored = apply_inverse(after, inv)
    assert frame_equal(restored, df)


@settings(max_examples=25, deadline=None)
@given(
    st.lists(
        st.none()
        | st.floats(
            allow_nan=False,
            allow_infinity=False,
            min_value=-1000,
            max_value=1000,
        ),
        min_size=1,
        max_size=20,
    )
)
def test_prop_fill_missing(values: list[float | None]) -> None:
    op = OPS["fill_missing"]
    df = pl.DataFrame({"amt": values}, schema={"amt": pl.Float64})
    params = {"column": "amt", "value": 0.0}
    after = op.apply(df, params)
    inv = op.inverse(df, after, params)
    restored = apply_inverse(after, inv)
    assert frame_equal(restored, df)


@settings(max_examples=25, deadline=None)
@given(
    st.lists(st.integers(min_value=-100, max_value=100), min_size=1, max_size=20),
    st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=20),
)
def test_prop_drop_column(c1: list[int], c2: list[str]) -> None:
    min_len = min(len(c1), len(c2))
    df = pl.DataFrame({"num": c1[:min_len], "txt": c2[:min_len]})
    op = OPS["drop_column"]
    params = {"column": "txt"}
    after = op.apply(df, params)
    inv = op.inverse(df, after, params)
    restored = apply_inverse(after, inv)
    assert frame_equal(restored, df)


@settings(max_examples=25, deadline=None)
@given(
    st.lists(
        st.sampled_from(["10", "20", "30", "40", "50"]),
        min_size=1,
        max_size=20,
    )
)
def test_prop_cast_type(values: list[str]) -> None:
    op = OPS["cast_type"]
    df = pl.DataFrame({"col": values})
    params = {"column": "col", "dtype": "int"}
    after = op.apply(df, params)
    inv = op.inverse(df, after, params)
    restored = apply_inverse(after, inv)
    assert frame_equal(restored, df)


@settings(max_examples=25, deadline=None)
@given(
    st.lists(st.integers(min_value=0, max_value=5), min_size=1, max_size=20),
    st.lists(st.sampled_from(["x", "y", "z"]), min_size=1, max_size=20),
)
def test_prop_deduplicate(c1: list[int], c2: list[str]) -> None:
    min_len = min(len(c1), len(c2))
    df = pl.DataFrame({"k": c1[:min_len], "v": c2[:min_len]})
    op = OPS["deduplicate"]
    params = {"subset": ["k", "v"]}
    after = op.apply(df, params)
    inv = op.inverse(df, after, params)
    restored = apply_inverse(after, inv)
    assert frame_equal(restored, df)


@settings(max_examples=25, deadline=None)
@given(
    st.lists(
        st.floats(allow_nan=False, allow_infinity=False, min_value=-100, max_value=100),
        min_size=1,
        max_size=20,
    ),
    st.lists(
        st.floats(allow_nan=False, allow_infinity=False, min_value=-100, max_value=100),
        min_size=1,
        max_size=20,
    ),
)
def test_prop_derive_column(a: list[float], b: list[float]) -> None:
    min_len = min(len(a), len(b))
    df = pl.DataFrame({"a": a[:min_len], "b": b[:min_len]})
    op = OPS["derive_column"]
    params = {
        "name": "res",
        "expression": {"op": "add", "args": [{"column": "a"}, {"column": "b"}]},
    }
    after = op.apply(df, params)
    inv = op.inverse(df, after, params)
    restored = apply_inverse(after, inv)
    assert frame_equal(restored, df)


@settings(max_examples=25, deadline=None)
@given(
    st.lists(
        st.sampled_from([
            '[]',
            '[{"val": 1}]',
            '[{"val": 2}, {"val": 3}]',
        ]),
        min_size=1,
        max_size=20,
    )
)
def test_prop_expand_nested(cells: list[str]) -> None:
    op = OPS["expand_nested"]
    df = pl.DataFrame({"id": list(range(len(cells))), "nested": cells})
    params = {"column": "nested", "key_column": "id", "child_table": "child"}
    after = op.apply(df, params)
    inv = op.inverse(df, after, params)
    restored = apply_inverse(after, inv)
    assert frame_equal(restored, df)


@settings(max_examples=25, deadline=None)
@given(st.lists(st.text(min_size=1, max_size=15), min_size=1, max_size=20))
def test_prop_standardise_format(strings: list[str]) -> None:
    op = OPS["standardise_format"]
    df = pl.DataFrame({"txt": strings})
    params = {"column": "txt", "format": "lower"}
    after = op.apply(df, params)
    inv = op.inverse(df, after, params)
    restored = apply_inverse(after, inv)
    assert frame_equal(restored, df)


# =====================================================================
# (c) Loss estimation tests
# =====================================================================


def test_loss_estimation() -> None:
    df = pl.DataFrame({
        "status": ["pending", "active", "pending", "active"],
        "num": [10.0, None, 20.0, None],
    })

    # Test estimate_step_loss for all 8 ops
    loss_replace = estimate_step_loss(
        df, "replace_value", {"column": "status", "mapping": {"pending": "active"}}
    )
    assert loss_replace.estimated_loss >= 0.0
    assert loss_replace.cells_affected == 2
    assert 0.0 <= loss_replace.cells_affected_pct <= 1.0

    loss_fill = estimate_step_loss(df, "fill_missing", {"column": "num", "value": 0.0})
    assert loss_fill.estimated_loss >= 0.0
    assert loss_fill.cells_affected == 2

    loss_drop = estimate_step_loss(df, "drop_column", {"column": "status"})
    assert loss_drop.estimated_loss >= 0.0
    assert loss_drop.cells_affected == 4

    # Unknown operation raises ValueError
    with pytest.raises(ValueError):
        estimate_step_loss(df, "non_existent_op", {})

    # Test cumulative_loss in 0..1
    losses = [
        LossEstimate("op1", 1, 1, 1, 0.01, 0.01),
        LossEstimate("op2", 2, 1, 2, 0.02, 0.02),
    ]
    cum = cumulative_loss(losses)
    assert 0.0 <= cum <= 1.0
    assert cum == pytest.approx(1.0 - (0.99 * 0.98))

    assert cumulative_loss([]) == 0.0
    assert cumulative_loss([LossEstimate("op", 1, 1, 1, 1.0, 1.0)]) == 1.0

    # check_threshold
    assert check_threshold(0.04, DEFAULT_LOSS_THRESHOLD) is True
    assert check_threshold(0.05, DEFAULT_LOSS_THRESHOLD) is True
    assert check_threshold(0.06, DEFAULT_LOSS_THRESHOLD) is False


# =====================================================================
# (d) Tests generation & checks execution
# =====================================================================


def test_tests_gen_pipeline(tmp_path: Path) -> None:
    profile = TableProfile(
        table_name="main",
        row_count=4,
        column_count=4,
        columns=[
            ColumnProfile(
                name="id",
                ordinal=0,
                physical_type="Int64",
                semantic_type="identifier",
                null_count=0,
                null_pct=0.0,
                distinct_count=4,
                min_value="1",
                max_value="4",
                mean_value=2.5,
                flags=["identifier"],
            ),
            ColumnProfile(
                name="status",
                ordinal=1,
                physical_type="String",
                semantic_type="category",
                null_count=0,
                null_pct=0.0,
                distinct_count=2,
                min_value=None,
                max_value=None,
                mean_value=None,
                flags=[],
            ),
            ColumnProfile(
                name="old_col",
                ordinal=2,
                physical_type="String",
                semantic_type="unknown",
                null_count=4,
                null_pct=1.0,
                distinct_count=0,
                min_value=None,
                max_value=None,
                mean_value=None,
                flags=["all_null"],
            ),
            ColumnProfile(
                name="amount",
                ordinal=3,
                physical_type="Float64",
                semantic_type="numeric",
                null_count=1,
                null_pct=0.25,
                distinct_count=3,
                min_value="10.0",
                max_value="30.0",
                mean_value=20.0,
                flags=[],
            ),
        ],
        issues=[],
    )

    plan_steps = [
        {"step_no": 1, "op": "fill_missing", "params": {"column": "amount", "value": 0.0}},
        {
            "step_no": 2,
            "op": "replace_value",
            "params": {"column": "status", "mapping": {"pending": "active"}},
        },
        {"step_no": 3, "op": "drop_column", "params": {"column": "old_col"}},
        {"step_no": 4, "op": "cast_type", "params": {"column": "amount", "dtype": "float"}},
        {"step_no": 5, "op": "deduplicate", "params": {"subset": ["id"]}},
    ]

    cases = generate_checks(plan_steps, profile)
    assert len(cases) >= 5

    check_names = {c.definition["check"] for c in cases}
    assert "no_nulls" in check_names
    assert "mapping_applied" in check_names
    assert "column_absent" in check_names
    assert "dtype_is" in check_names
    assert "unique" in check_names

    # Verify conforming dataframe
    conforming_df = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "status": ["active", "active", "active", "active"],
        "amount": [10.0, 20.0, 30.0, 0.0],
    })
    results_pass = run_checks(cases, conforming_df)
    assert all(r.passed for r in results_pass), [r for r in results_pass if not r.passed]

    # Verify violating dataframe (contains null in amount, wrong values in status, present old_col)
    violating_df = pl.DataFrame({
        "id": [1, 1, 3, 4],  # duplicate id -> violates unique
        "status": ["invalid_status", "active", "pending", "active"],  # violates mapping_applied
        "old_col": ["still_here", "x", "y", "z"],  # violates column_absent
        "amount": [10.0, None, 30.0, 0.0],  # violates no_nulls
    })
    results_fail = run_checks(cases, violating_df)
    failed_results = [r for r in results_fail if not r.passed]
    assert len(failed_results) >= 3

    # Test export_pytest
    test_file = tmp_path / "test_generated_suite.py"
    export_pytest(cases, test_file)
    assert test_file.exists()
    content = test_file.read_text(encoding="utf-8")
    assert "from conftest import load_table" in content
    assert "def test_" in content
