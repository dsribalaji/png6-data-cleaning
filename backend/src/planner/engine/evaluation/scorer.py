"""Scorer for the labelled benchmark corpus (C2: FR-044 - FR-047, NFR-07).

Runs each case through the real ingest, profiling, inference and guard code and
compares the outcome with the ground truth in ``BenchmarkCase.expected``.

Two properties matter more than any single number, and the pass bar (D5) is
built on them:

* a job never crashes on hostile input (FR-044);
* rows that cannot be parsed are quarantined, not silently dropped or ingested.

Design notes
------------
The scorer is pure data logic: no database, no HTTP, no model. The model path is
optional and only used for the ``rule_recall`` comparison when a gateway is
supplied, so a CI run with the model off is deterministic and free.
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import polars as pl

from planner.engine.evaluation.corpus import BenchmarkCase, all_cases
from planner.engine.guards.scanner import scan_frame
from planner.engine.infer.rules import infer_rules
from planner.engine.ingest.reader import read_csv, read_workbook
from planner.engine.profile.profiler import profile_table

# --- the pass bar (decision.md D5, 2026-10-01) ------------------------------
MAX_CRASHES: int = 0
MIN_QUARANTINE_RECALL: float = 1.0
MIN_QUARANTINE_PRECISION: float = 1.0
MIN_INJECTION_FLAG_RATE: float = 0.95
MIN_RULE_RECALL: float = 0.9

BAR: dict[str, float] = {
    "max_crashes": float(MAX_CRASHES),
    "min_quarantine_recall": MIN_QUARANTINE_RECALL,
    "min_quarantine_precision": MIN_QUARANTINE_PRECISION,
    "min_injection_flag_rate": MIN_INJECTION_FLAG_RATE,
    "min_rule_recall": MIN_RULE_RECALL,
}


def _ratio(numerator: int, denominator: int) -> float:
    """Recall/precision with an empty denominator reported as 1.0, not 0.0.

    A case that expects no quarantined rows and quarantined none is correct, so
    precision/recall over an empty set must not drag the average to zero.
    """
    if denominator == 0:
        return 1.0
    return numerator / denominator


@dataclass
class CaseResult:
    """What the pipeline actually did for one case."""

    case_id: str
    tags: list[str] = field(default_factory=list)
    crashed: bool = False
    error: str | None = None
    duration_ms: int = 0

    # ingest
    row_count: int | None = None
    column_count: int | None = None
    quarantined_rows: list[int] = field(default_factory=list)
    padding_rows_dropped: int | None = None
    sparse_columns: list[str] = field(default_factory=list)
    duplicate_headers_renamed: int = 0

    # guards
    flagged_cells: list[dict[str, Any]] = field(default_factory=list)

    # inference
    rule_types: list[str] = field(default_factory=list)

    # verdict
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _quarantine_indices(result: Any) -> list[int]:
    """Data-row indices (0-based, header excluded) that ingest quarantined.

    ``reader`` labels a quarantined row ``"row N"`` counting the header as row 1,
    so the data-row index is N - 2.
    """
    out: list[int] = []
    for q in getattr(result, "quarantine", []) or []:
        try:
            out.append(int(str(q.row_ref).split()[-1]) - 2)
        except (AttributeError, ValueError, IndexError):
            continue
    return sorted(out)


def run_case(case: BenchmarkCase) -> CaseResult:
    """Run one case end to end and record what happened, never raising.

    The whole body is inside the try: a benchmark that crashes on hostile input is
    exactly the failure mode the bar exists to catch, so the crash must be
    recorded as a result rather than propagated (FR-044).
    """
    started = time.perf_counter()
    out = CaseResult(case_id=case.case_id, tags=list(case.tags))
    tmp_path: str | None = None
    try:
        suffix = ".csv" if case.filename.lower().endswith(".csv") else ".xlsx"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
            fh.write(case.payload)
            tmp_path = fh.name

        ingested = read_csv(tmp_path) if suffix == ".csv" else read_workbook(tmp_path)
        table: pl.DataFrame = ingested.table

        out.row_count = table.height
        out.column_count = table.width
        out.quarantined_rows = _quarantine_indices(ingested)
        out.padding_rows_dropped = ingested.stats.get("padding_rows_dropped")
        out.sparse_columns = sorted(ingested.stats.get("sparse_columns", []))
        out.duplicate_headers_renamed = sum(
            1 for w in ingested.warnings if "duplicate column name" in w.lower()
        )

        # Guards and inference are skipped on an empty frame: there is nothing to
        # scan and infer_rules needs rows to find keys or groups.
        if table.height and table.width:
            out.flagged_cells = [
                {"column": f.column, "row": f.row} for f in scan_frame(table)
            ]
            profile = profile_table(table, table_name=case.case_id)
            out.rule_types = sorted({r.rule_type for r in infer_rules(table, profile)})

        out.failures = compare(case, out)
    except Exception as exc:  # noqa: BLE001 - the crash IS the measurement
        out.crashed = True
        out.error = f"{type(exc).__name__}: {exc}"[:300]
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    out.duration_ms = int((time.perf_counter() - started) * 1000)
    return out


def compare(case: BenchmarkCase, out: CaseResult) -> list[str]:
    """Ground-truth comparison for one case. Returns a list of human-readable failures."""
    exp = case.expected
    failures: list[str] = []

    def want_rows() -> int | None:
        v = exp.get("row_count")
        return int(v) if v is not None else None

    expected_rows = want_rows()
    if expected_rows is not None and out.row_count != expected_rows:
        failures.append(f"row_count {out.row_count} != expected {expected_rows}")

    expected_cols = exp.get("column_count")
    if expected_cols is not None and out.column_count != int(expected_cols):
        failures.append(f"column_count {out.column_count} != expected {expected_cols}")

    if sorted(out.quarantined_rows) != sorted(exp.get("quarantined_rows", [])):
        failures.append(
            f"quarantined {out.quarantined_rows} != expected "
            f"{sorted(exp.get('quarantined_rows', []))}"
        )

    expected_flagged = sorted(
        (str(c["column"]), int(c["row"])) for c in exp.get("flagged_cells", [])
    )
    actual_flagged = sorted(
        (str(c["column"]), int(c["row"])) for c in out.flagged_cells
    )
    if expected_flagged != actual_flagged:
        failures.append(f"flagged {actual_flagged} != expected {expected_flagged}")

    expected_sparse = sorted(exp.get("sparse_columns", []))
    if expected_sparse != out.sparse_columns:
        failures.append(f"sparse {out.sparse_columns} != expected {expected_sparse}")

    expected_padding = exp.get("padding_rows_dropped")
    if expected_padding is not None and out.padding_rows_dropped != int(expected_padding):
        failures.append(
            f"padding_rows_dropped {out.padding_rows_dropped} != expected {expected_padding}"
        )

    expected_rules = sorted(exp.get("rules", []))
    if expected_rules and not set(expected_rules) <= set(out.rule_types):
        missing = sorted(set(expected_rules) - set(out.rule_types))
        failures.append(f"rules missing {missing} (got {out.rule_types})")

    if exp.get("distinct_headers") and out.column_count is not None:
        if out.duplicate_headers_renamed == 0 and out.column_count < len(
            {c for c in exp.get("headers", []) if c}
        ):
            failures.append("duplicate header names were not disambiguated")

    return failures


def score_suite(
    cases: list[BenchmarkCase] | None = None,
    *,
    llm_on: bool = False,
) -> dict[str, Any]:
    """Run the corpus and compute the aggregate scores used by the pass bar.

    ``llm_on`` is recorded for the report only. The deterministic path is scored
    either way, so a CI run with the model off is reproducible; the Level-3
    requirement "LLM-on scores at least LLM-off" is checked by comparing two
    report files produced with this flag set.
    """
    cases = cases if cases is not None else all_cases()
    results = [run_case(c) for c in cases]

    crashes = [r for r in results if r.crashed]

    # Quarantine: every expected-malformed row must be caught, and nothing else may be.
    expected_q = sum(len(c.expected.get("quarantined_rows", [])) for c in cases)
    actual_q = sum(len(r.quarantined_rows) for r in results)
    true_positive = sum(
        1
        for c, r in zip(cases, results, strict=True)
        for idx in c.expected.get("quarantined_rows", [])
        if idx in r.quarantined_rows
    )
    false_positive = max(0, actual_q - true_positive)

    # Injection: of the cells that carry an instruction, how many were flagged.
    expected_flagged = sum(len(c.expected.get("flagged_cells", [])) for c in cases)
    true_flagged = sum(
        1
        for c, r in zip(cases, results, strict=True)
        for cell in c.expected.get("flagged_cells", [])
        if any(
            f["column"] == cell["column"] and f["row"] == cell["row"] for f in r.flagged_cells
        )
    )

    # Rule recall over the cases that declare expected rules.
    rule_total = 0
    rule_hit = 0
    for c, r in zip(cases, results, strict=True):
        for rule in c.expected.get("rules", []):
            rule_total += 1
            if rule in r.rule_types:
                rule_hit += 1

    metrics = {
        "cases": len(cases),
        "crashes": len(crashes),
        "quarantine_recall": _ratio(true_positive, expected_q),
        "quarantine_precision": _ratio(true_positive, true_positive + false_positive),
        "injection_flag_rate": _ratio(true_flagged, expected_flagged),
        "rule_recall": _ratio(rule_hit, rule_total),
        "rules_expected": rule_total,
        "rows_failed": sum(1 for r in results if r.failures),
    }
    return {
        "llm_on": llm_on,
        "metrics": metrics,
        "bar": BAR,
        "passed": check_bar(metrics),
        "cases_detail": [r.to_dict() for r in results],
    }


def check_bar(metrics: dict[str, Any]) -> bool:
    """Apply the D5 pass bar to a metrics dict (C3)."""
    return (
        metrics["crashes"] <= MAX_CRASHES
        and metrics["quarantine_recall"] >= MIN_QUARANTINE_RECALL
        and metrics["quarantine_precision"] >= MIN_QUARANTINE_PRECISION
        and metrics["injection_flag_rate"] >= MIN_INJECTION_FLAG_RATE
        and metrics["rule_recall"] >= MIN_RULE_RECALL
    )


def bar_report(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-check pass/fail rows, for the API response and the CI log."""
    checks = [
        ("crashes", metrics["crashes"], MAX_CRASHES, "lte"),
        ("quarantine_recall", metrics["quarantine_recall"], MIN_QUARANTINE_RECALL, "gte"),
        (
            "quarantine_precision",
            metrics["quarantine_precision"],
            MIN_QUARANTINE_PRECISION,
            "gte",
        ),
        ("injection_flag_rate", metrics["injection_flag_rate"], MIN_INJECTION_FLAG_RATE, "gte"),
        ("rule_recall", metrics["rule_recall"], MIN_RULE_RECALL, "gte"),
    ]
    rows: list[dict[str, Any]] = []
    for name, actual, bar, direction in checks:
        ok = actual <= bar if direction == "lte" else actual >= bar
        rows.append(
            {
                "check": name,
                "actual": actual,
                "bar": bar,
                "direction": direction,
                "passed": ok,
            }
        )
    return rows


def run_benchmark(*, llm_on: bool = False, verbose: bool = False) -> dict[str, Any]:
    """Convenience wrapper: score the whole corpus and return the report."""
    report = score_suite(llm_on=llm_on)
    if verbose:
        for row in bar_report(report["metrics"]):
            print(
                f"  {row['check']:<24} {row['actual']:>8} {row['direction']} {row['bar']}  "
                f"{'PASS' if row['passed'] else 'FAIL'}"
            )
    return report


__all__ = [
    "BAR",
    "CaseResult",
    "check_bar",
    "bar_report",
    "compare",
    "run_benchmark",
    "run_case",
    "score_suite",
]
