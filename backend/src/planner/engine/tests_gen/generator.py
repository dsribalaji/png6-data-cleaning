"""Test case generator for dataset transformation plans.

Pure data logic - no FastAPI/DB imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from planner.engine.profile.profiler import TableProfile

SUPPORTED_CHECKS = {
    "no_nulls",
    "unique",
    "matches_regex",
    "row_count_equals",
    "row_count_gt",
    "values_in",
    "dtype_is",
    "column_absent",
    "sum_equals",
    "arithmetic_holds",
}


@dataclass
class TestCase:
    __test__ = False
    name: str
    type: str  # "unit" | "integration"
    target: str | None
    definition: dict[str, Any]


@dataclass
class TestResult:
    __test__ = False
    name: str
    passed: bool
    detail: str


def generate_checks(plan_steps: list[dict[str, Any]], profile: TableProfile) -> list[TestCase]:
    """Generate unit and integration test cases from plan steps and table profile."""
    cases: list[TestCase] = []
    dropped_columns: set[str] = set()

    dtype_map = {
        "float": "Float64",
        "int": "Int64",
        "string": "String",
        "date": "Date",
    }


    for step in plan_steps:
        step_no = step.get("step_no", 0)
        op = step.get("op", "")
        params = step.get("params", {})

        if op == "replace_value":
            col = params.get("column", "")
            mapping = params.get("mapping", {})
            cases.append(
                TestCase(
                    name=f"step_{step_no}_replace_value_{col}",
                    type="unit",
                    target=col,
                    definition={
                        "check": "mapping_applied",
                        "column": col,
                        "mapping": mapping,
                        "table": "main",
                    },
                )
            )

        elif op == "fill_missing":
            col = params.get("column", "")
            cases.append(
                TestCase(
                    name=f"step_{step_no}_fill_missing_{col}",
                    type="unit",
                    target=col,
                    definition={
                        "check": "no_nulls",
                        "column": col,
                        "table": "main",
                    },
                )
            )

        elif op == "drop_column":
            col = params.get("column", "")
            dropped_columns.add(col)
            cases.append(
                TestCase(
                    name=f"step_{step_no}_drop_column_{col}",
                    type="unit",
                    target=col,
                    definition={
                        "check": "column_absent",
                        "column": col,
                        "table": "main",
                    },
                )
            )

        elif op == "cast_type":
            col = params.get("column", "")
            dt_param = params.get("dtype", "")
            target_dt_str = dtype_map.get(dt_param, dt_param)
            cases.append(
                TestCase(
                    name=f"step_{step_no}_cast_type_{col}",
                    type="unit",
                    target=col,
                    definition={
                        "check": "dtype_is",
                        "column": col,
                        "dtype": target_dt_str,
                        "table": "main",
                    },
                )
            )

        elif op == "expand_nested":
            child_table = params.get("child_table", "child")
            cases.append(
                TestCase(
                    name=f"step_{step_no}_expand_nested_{child_table}",
                    type="integration",
                    target=child_table,
                    definition={
                        "check": "row_count_gt",
                        "table": child_table,
                        "min": 1,
                    },
                )
            )

        elif op == "derive_column":
            name = params.get("name", "")
            cases.append(
                TestCase(
                    name=f"step_{step_no}_derive_column_{name}",
                    type="unit",
                    target=name,
                    definition={
                        "check": "no_nulls",
                        "column": name,
                        "table": "main",
                    },
                )
            )

        elif op == "deduplicate":
            subset = params.get("subset")
            is_single = subset is not None and len(subset) == 1
            # No subset = whole-row duplicates: check every column present at check
            # time (earlier steps may have dropped some of the profiled columns).
            definition: dict[str, Any] = {"check": "unique", "table": "main"}
            if subset is not None:
                definition["columns"] = list(subset)
            cases.append(
                TestCase(
                    name=f"step_{step_no}_deduplicate",
                    type="unit" if is_single else "integration",
                    target=subset[0] if is_single else None,
                    definition=definition,
                )
            )

    # Checks derived from TableProfile:
    # 1. Identifier columns -> unique check
    for col_prof in profile.columns:
        is_identifier = col_prof.semantic_type == "identifier" or "identifier" in col_prof.flags
        # Only assert uniqueness the source actually had (null counts as one value);
        # repeated IDs with differing content are a data finding, not a cleaning failure.
        was_unique = profile.row_count > 0 and (
            col_prof.distinct_count + (1 if col_prof.null_count else 0) >= profile.row_count
        )
        if is_identifier and was_unique and col_prof.name not in dropped_columns:
            cases.append(
                TestCase(
                    name=f"profile_unique_{col_prof.name}",
                    type="unit",
                    target=col_prof.name,
                    definition={
                        "check": "unique",
                        "columns": [col_prof.name],
                        "table": "main",
                    },
                )
            )

    # 2. All-null columns that were dropped -> column_absent
    for col_prof in profile.columns:
        is_all_null = (
            "all_null" in col_prof.flags
            or col_prof.null_pct == 1.0
            or (profile.row_count > 0 and col_prof.null_count == profile.row_count)
        )
        if is_all_null and col_prof.name in dropped_columns:
            # Check if an explicit profile test case should be present
            # Avoid duplicate definition for same column if already added
            already_added = any(
                c.definition.get("check") == "column_absent"
                and c.definition.get("column") == col_prof.name
                and c.name.startswith("profile_")
                for c in cases
            )
            if not already_added:
                cases.append(
                    TestCase(
                        name=f"profile_column_absent_{col_prof.name}",
                        type="unit",
                        target=col_prof.name,
                        definition={
                            "check": "column_absent",
                            "column": col_prof.name,
                            "table": "main",
                        },
                    )
                )

    return cases
