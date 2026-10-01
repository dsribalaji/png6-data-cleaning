from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import dateutil.parser
import polars as pl

from planner.engine.nested import parse_nested


@dataclass
class ColumnProfile:
    name: str
    ordinal: int
    physical_type: str
    semantic_type: str
    null_count: int
    null_pct: float
    distinct_count: int
    min_value: str | None
    max_value: str | None
    mean_value: float | None
    flags: list[str]


@dataclass
class TableProfile:
    table_name: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    issues: list[str]


def _check_nested_json(values: list[Any]) -> bool:
    """Nested when at least half the values parse as records (JSON or repairable)."""
    if not values:
        return False
    parsed = sum(1 for v in values if parse_nested(v).status in ("ok", "repaired", "partial"))
    return (parsed / len(values)) >= 0.5


def _check_numeric_text(values: list[Any]) -> bool:
    if not values:
        return False
    parsed_count = 0
    for v in values:
        s = str(v).replace("$", "").replace(",", "").strip()
        if not s:
            continue
        try:
            float(s)
            parsed_count += 1
        except ValueError:
            continue
    return (parsed_count / len(values)) >= 0.8


def _check_date_strings(values: list[Any]) -> bool:
    if not values:
        return False
    parsed_count = 0
    for v in values:
        s = str(v).strip()
        if len(s) < 4:
            continue
        try:
            dateutil.parser.parse(s)
            parsed_count += 1
        except Exception:
            continue
    return (parsed_count / len(values)) >= 0.8


# A short alphanumeric token with an internal separator or digit run, e.g.
# "SKU-1001", "EMP-001", "PO-1424". Shape-based on purpose: it must recognise a
# key column whatever the dataset calls it (FR-050), so the column NAME is not
# part of the test.
_CODE_LIKE = re.compile(r"^[A-Za-z]{1,10}[-_ ]?\d{2,12}$")


def _check_code_strings(values: list[Any]) -> bool:
    """True when most values look like codes rather than prose or amounts.

    Used to recognise an identifier column whose name carries no hint
    ("sku", "ref"), which a name-based rule misses.
    """
    sample = [str(v).strip() for v in values if v is not None and str(v).strip()]
    if not sample:
        return False
    hits = sum(1 for v in sample if _CODE_LIKE.match(v))
    return hits / len(sample) >= 0.9


def _check_boolean_strings(values: list[Any]) -> bool:
    allowed = {"true", "false", "0", "1", "yes", "no", "t", "f", "y", "n"}
    return all(str(v).strip().lower() in allowed for v in values)


def profile_table(df: pl.DataFrame, table_name: str = "dataset") -> TableProfile:
    row_count = len(df)
    column_count = len(df.columns)
    column_profiles: list[ColumnProfile] = []

    for ordinal, col_name in enumerate(df.columns):
        s = df[col_name]
        physical_type = str(s.dtype)
        null_count = s.null_count()
        null_pct = round(null_count / row_count, 4) if row_count > 0 else 0.0

        non_null_series = s.drop_nulls()
        non_null_count = len(non_null_series)
        distinct_count = non_null_series.n_unique()
        distinct_ratio = (distinct_count / row_count) if row_count > 0 else 0.0

        # Min, max, mean
        min_val: Any = non_null_series.min() if non_null_count > 0 else None
        max_val: Any = non_null_series.max() if non_null_count > 0 else None
        min_value: str | None = str(min_val) if min_val is not None else None
        max_value: str | None = str(max_val) if max_val is not None else None

        mean_value: float | None = None
        if s.dtype.is_numeric() and non_null_count > 0:
            m = non_null_series.mean()
            mean_value = float(m) if m is not None else None

        # Determine semantic type & flags
        flags: list[str] = []
        semantic_type = "unknown"
        col_lower = col_name.lower()
        is_id_name = bool(re.search(r"id|number|code", col_lower))
        is_curr_name = bool(re.search(r"amount|price|total|vat|tax|cost", col_lower))

        if non_null_count == 0:
            semantic_type = "unknown"
        elif s.dtype in (pl.Date, pl.Datetime):
            semantic_type = "date"
        elif s.dtype == pl.Boolean:
            semantic_type = "boolean"
        elif s.dtype.is_numeric():
            if is_id_name and distinct_ratio > 0.9:
                semantic_type = "identifier"
            elif s.dtype.is_integer():
                semantic_type = "integer"
            else:
                semantic_type = "float"
        elif s.dtype in (pl.String, pl.Utf8, pl.Object):
            sample_values = non_null_series.to_list()
            if _check_nested_json(sample_values):
                semantic_type = "nested_json"
            elif _check_numeric_text(sample_values):
                flags.append("numeric_as_text")
                if is_curr_name:
                    semantic_type = "currency"
                else:
                    semantic_type = "numeric_text"
            elif _check_date_strings(sample_values):
                semantic_type = "date"
            elif is_id_name and distinct_ratio > 0.9:
                semantic_type = "identifier"
            elif distinct_ratio > 0.9 and _check_code_strings(sample_values):
                # A near-unique column of code-shaped values is a key even when
                # its name says nothing ("sku", "ref", "code_ref").
                semantic_type = "identifier"
            elif distinct_count == 2 and _check_boolean_strings(sample_values):
                semantic_type = "boolean"
            elif distinct_count <= 50:
                semantic_type = "category"
            else:
                semantic_type = "free_text"
        else:
            if distinct_count <= 50:
                semantic_type = "category"
            else:
                semantic_type = "unknown"

        # Apply flags
        if null_count == row_count or row_count == 0:
            flags.append("all_null")
        if null_pct >= 0.95:
            flags.append("sparse_95")
        if distinct_count == 1 and null_count == 0:
            flags.append("constant")
        if semantic_type == "nested_json":
            flags.append("nested_json")
        if distinct_count > 50:
            flags.append("high_cardinality")

        column_profiles.append(
            ColumnProfile(
                name=col_name,
                ordinal=ordinal,
                physical_type=physical_type,
                semantic_type=semantic_type,
                null_count=null_count,
                null_pct=null_pct,
                distinct_count=distinct_count,
                min_value=min_value,
                max_value=max_value,
                mean_value=mean_value,
                flags=flags,
            )
        )

    # Table issues
    issues: list[str] = []
    has_all_null = any("all_null" in c.flags for c in column_profiles)
    nested_json_cols = [c.name for c in column_profiles if "nested_json" in c.flags]
    has_numeric_as_text = any("numeric_as_text" in c.flags for c in column_profiles)
    has_sparse = any("sparse_95" in c.flags for c in column_profiles)

    if has_all_null:
        issues.append("all-null-columns")
    if nested_json_cols:
        issues.append(f"nested-json-columns: {', '.join(nested_json_cols)}")
    if has_numeric_as_text:
        issues.append("numeric-as-text-columns")
    if has_sparse:
        issues.append("sparse-columns")

    return TableProfile(
        table_name=table_name,
        row_count=row_count,
        column_count=column_count,
        columns=column_profiles,
        issues=issues,
    )
