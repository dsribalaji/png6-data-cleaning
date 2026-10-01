"""B7: cross-field fill is proposed, and never auto-accepted (FR-019, OQ-12)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import polars as pl

from planner.engine.evaluation.corpus import all_cases
from planner.engine.infer.rules import infer_rules
from planner.engine.ingest.reader import read_csv
from planner.engine.profile.profiler import profile_table
from planner.modules.planning.tasks import (
    LOW_CONFIDENCE,
    NEVER_AUTO_ACCEPT,
    default_decision,
    step_decision,
)


def _load(case_id: str) -> tuple[pl.DataFrame, list[object]]:
    case = next(c for c in all_cases() if c.case_id == case_id)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as fh:
        fh.write(case.payload)
        path = fh.name
    try:
        table = read_csv(Path(path)).table
    finally:
        Path(path).unlink()
    return table, infer_rules(table, profile_table(table, table_name=case_id))


def test_cross_field_fill__missings_with_a_constant_sibling__rule_is_inferred() -> None:
    """The rule type exists and fires: a golden case on the reference-file shape."""
    _, rules = _load("cross_field_fill")
    fills = [r for r in rules if r.rule_type == "cross_field_fill"]
    assert fills, [r.rule_type for r in rules]
    expression = fills[0].expression
    assert expression["target"] == "invoice_date"
    assert expression["source"] == "batch"
    assert expression["value"] == "APR-A"


def test_cross_field_fill__step_is_never_auto_accepted() -> None:
    """OQ-12 / decision.md P1: the planner must not invent a value unattended."""
    # Confidence is 0.85 and loss is 0, so the generic rule WOULD accept it. The
    # never-auto-accept rule has to override that.
    assert step_decision("fill_missing", 0.0, 0.05, 0.85) == "pending"
    assert step_decision("derive_column", 0.0, 0.05, 0.99) == "pending"


def test_step_decision__lossless_non_filling_ops_still_auto_accept() -> None:
    assert step_decision("drop_column", 0.0, 0.05, 1.0) == "accepted"
    assert step_decision("expand_nested", 0.0, 0.05, 0.9) == "accepted"


def test_default_decision__unchanged_for_the_ordinary_threshold_rules() -> None:
    """The precedence rule only adds a veto; the threshold/confidence logic is intact."""
    assert default_decision(0.0, 0.05, 1.0) == "accepted"
    assert default_decision(0.06, 0.05, 1.0) == "pending"  # over the loss limit
    assert default_decision(0.0, 0.05, LOW_CONFIDENCE - 0.01) == "pending"  # low confidence


def test_never_auto_accept__covers_every_value_inventing_operation() -> None:
    """Guard: any operation that writes a value not present in the source."""
    from planner.engine.ops.base import OPS

    assert NEVER_AUTO_ACCEPT <= set(OPS.keys())
    assert {"fill_missing", "derive_column"} <= NEVER_AUTO_ACCEPT
