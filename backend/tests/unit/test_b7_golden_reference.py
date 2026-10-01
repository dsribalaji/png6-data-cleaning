"""B7 golden test on the real reference workbook: restraint is the correct behavior."""

from __future__ import annotations

import tempfile
from pathlib import Path

import polars as pl

from planner.engine.evaluation.corpus import all_cases
from planner.engine.infer.rules import infer_rules
from planner.engine.ingest.reader import read_csv, read_workbook
from planner.engine.profile.profiler import profile_table
from planner.modules.planning.tasks import NEVER_AUTO_ACCEPT, step_decision


def _load_corpus_table(case_id: str) -> pl.DataFrame:
    case = next(c for c in all_cases() if c.case_id == case_id)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as fh:
        fh.write(case.payload)
        path = fh.name
    try:
        return read_csv(Path(path)).table
    finally:
        Path(path).unlink()


def test_reference_workbook__cross_field_fill_does_not_fire_without_genuine_candidate() -> None:
    REFERENCE = Path(__file__).parents[3] / "data" / "reference" / "VendorInvoices_uncleaned.xlsx"
    table = read_workbook(REFERENCE).table
    rules = infer_rules(table, profile_table(table, table_name="reference"))
    fills = [r for r in rules if r.rule_type == "cross_field_fill"]
    # Restraint is the correct behavior: on the real reference workbook, null
    # columns have no genuine sibling holding an answer (only customer_name="HAC"
    # everywhere, and filling a PO/VAT number with a customer name would be
    # inventing data, forbidden by OQ-12 labelled-nulls-by-default).
    assert fills == []


def test_reference_workbook__positive_control_corpus_case_still_fires() -> None:
    table = _load_corpus_table("cross_field_fill")
    rules = infer_rules(table, profile_table(table, table_name="cross_field_fill"))
    fills = [r for r in rules if r.rule_type == "cross_field_fill"]
    assert len(fills) == 1
    expression = fills[0].expression
    assert expression["target"] == "invoice_date"
    assert expression["source"] == "batch"
    assert expression["value"] == "APR-A"


def test_reference_workbook__fill_missing_step_is_never_auto_accepted() -> None:
    assert "fill_missing" in NEVER_AUTO_ACCEPT
    for c in (0.5, 0.85, 0.99):
        assert step_decision("fill_missing", 0.0, 0.05, c) == "pending"
    assert step_decision("fill_missing", 0.0, 0.0, 1.0) == "pending"
