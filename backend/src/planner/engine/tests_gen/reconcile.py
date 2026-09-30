"""Source-vs-output reconciliation (FR-042). Pure data logic, dataset-agnostic.

Totals are recomputed independently from the ORIGINAL frame (nested JSON is re-parsed
here, not taken from the executed child table), so a lossy step cannot hide itself.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import polars as pl

_TOL = 0.01  # one cent
_STRIP = re.compile(r"[\$,\s]")


@dataclass(frozen=True)
class Reconciliation:
    check_name: str
    source_value: float
    output_value: float
    ok: bool


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(_STRIP.sub("", str(value)))
    except ValueError:
        return None


def _items(cell: Any) -> list[dict[str, Any]]:
    if not isinstance(cell, str) or not cell:
        return []
    try:
        val = json.loads(cell)
    except ValueError:
        return []
    if isinstance(val, dict):
        return [val]
    return [x for x in val if isinstance(x, dict)] if isinstance(val, list) else []


def _sum(series: pl.Series) -> float:
    return float(series.cast(pl.Float64, strict=False).fill_null(0).sum())


def _check(name: str, src: float, out: float) -> Reconciliation:
    return Reconciliation(name, round(src, 2), round(out, 2), abs(src - out) < _TOL)


def reconcile(
    before: pl.DataFrame,
    after: pl.DataFrame,
    side_tables: dict[str, pl.DataFrame],
    steps: list[dict[str, Any]],
) -> list[Reconciliation]:
    """Compare the source frame with the executed output tables.

    ``steps`` are the executed plan steps ({"operation", "parameters"}).
    """
    ops = [(s.get("operation") or s.get("op"), s.get("parameters") or s.get("params") or {}) for s in steps]
    out: list[Reconciliation] = []

    # 1. Parent row count (deduplicate may legitimately remove rows).
    dedup = any(op == "deduplicate" for op, _ in ops)
    out.append(
        Reconciliation(
            "row_count",
            before.height,
            after.height,
            after.height <= before.height if dedup else after.height == before.height,
        )
    )

    # 2. Numeric column totals; a dropped redundant column is checked against its twin.
    twins = {p["column"]: p["redundant_with"] for op, p in ops if op == "drop_column" and p.get("redundant_with")}
    numeric = [c for c in before.columns if before[c].dtype.is_numeric()]
    sums: dict[str, tuple[float, float]] = {}
    for col in numeric:
        target = col if col in after.columns else twins.get(col)
        if target is None or target not in after.columns:
            continue
        sums[col] = (_sum(before[col]), _sum(after[target]))
        label = col if target == col else f"{col} (= {target})"
        out.append(_check(f"sum:{label}", *sums[col]))

    # 3. Gross total: the largest-valued numeric column of the source table.
    if sums:
        gross_col = max(sums, key=lambda c: abs(sums[c][0]))
        out.append(_check(f"gross_total:{gross_col}", *sums[gross_col]))

    # 4. Nested expansions: item count and every numeric item field, re-parsed from source.
    for op, p in ops:
        if op != "expand_nested" or p.get("column") not in before.columns:
            continue
        table = side_tables.get(p.get("child_table", ""))
        items = [it for cell in before[p["column"]].to_list() for it in _items(cell)]
        out.append(
            Reconciliation(f"row_count:{p['child_table']}", len(items), 0 if table is None else table.height,
                           table is not None and table.height == len(items))
        )
        if table is None:
            continue
        for col in table.columns:
            if not table[col].dtype.is_numeric():
                continue
            src = sum(v for it in items if (v := _num(it.get(col))) is not None)
            out.append(_check(f"sum:{p['child_table']}.{col}", src, _sum(table[col])))

    return out
