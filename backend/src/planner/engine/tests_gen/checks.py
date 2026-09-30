"""Test execution and pytest exporter for generated test cases.

Pure data logic - no FastAPI/DB imports.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
import polars as pl

from planner.engine.ops.base import str_to_dtype
from planner.engine.tests_gen.generator import TestCase, TestResult


def run_checks(
    cases: list[TestCase],
    df: pl.DataFrame,
    tables: dict[str, pl.DataFrame] | None = None,
) -> list[TestResult]:
    """Execute generated test cases against DataFrame(s).

    Never raises on bad data; records TestResult(passed=False, ...).
    """
    results: list[TestResult] = []
    tables_map = tables or {}

    for case in cases:
        try:
            defn = case.definition
            check = defn.get("check")
            table_name = defn.get("table", "main")

            if table_name == "main":
                target_df = df
            elif table_name in tables_map:
                target_df = tables_map[table_name]
            else:
                results.append(
                    TestResult(
                        name=case.name,
                        passed=False,
                        detail=f"Table '{table_name}' not found in provided tables",
                    )
                )
                continue

            if check == "no_nulls":
                col = defn.get("column", "")
                if col not in target_df.columns:
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=False,
                            detail=f"Column '{col}' does not exist",
                        )
                    )
                else:
                    null_cnt = target_df[col].null_count()
                    passed = null_cnt == 0
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=passed,
                            detail=f"Column '{col}' has {null_cnt} nulls"
                            if not passed
                            else f"Column '{col}' has 0 nulls",
                        )
                    )

            elif check == "unique":
                cols = defn.get("columns")
                if not cols:
                    single_col = defn.get("column")
                    cols = [single_col] if single_col else list(target_df.columns)

                missing_cols = [c for c in cols if c not in target_df.columns]
                if missing_cols:
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=False,
                            detail=f"Columns {missing_cols} missing from table",
                        )
                    )
                else:
                    total_rows = target_df.height
                    unique_rows = target_df.select(cols).n_unique()
                    passed = total_rows == unique_rows
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=passed,
                            detail=f"{unique_rows}/{total_rows} unique rows across {cols}",
                        )
                    )

            elif check == "matches_regex":
                col = defn.get("column", "")
                pattern = defn.get("pattern", "")
                if col not in target_df.columns:
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=False,
                            detail=f"Column '{col}' does not exist",
                        )
                    )
                else:
                    try:
                        s = target_df[col].drop_nulls().cast(pl.String)
                        passed = bool(s.str.contains(pattern).all())
                        results.append(
                            TestResult(
                                name=case.name,
                                passed=passed,
                                detail=f"Pattern '{pattern}' matched all non-null values"
                                if passed
                                else f"Pattern '{pattern}' did not match all non-null values",
                            )
                        )
                    except Exception as exc:
                        results.append(
                            TestResult(
                                name=case.name,
                                passed=False,
                                detail=f"Regex match failed with error: {exc}",
                            )
                        )

            elif check == "row_count_equals":
                expected = defn.get("expected")
                actual = target_df.height
                passed = actual == expected
                results.append(
                    TestResult(
                        name=case.name,
                        passed=passed,
                        detail=f"Expected {expected} rows, got {actual}",
                    )
                )

            elif check == "row_count_gt":
                min_rows = defn.get("min", 1)
                actual = target_df.height
                passed = actual >= min_rows
                results.append(
                    TestResult(
                        name=case.name,
                        passed=passed,
                        detail=f"Expected >= {min_rows} rows, got {actual}",
                    )
                )

            elif check == "values_in":
                col = defn.get("column", "")
                allowed = set(defn.get("allowed", []))
                if col not in target_df.columns:
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=False,
                            detail=f"Column '{col}' does not exist",
                        )
                    )
                else:
                    vals = target_df[col].drop_nulls().to_list()
                    disallowed = [x for x in vals if x not in allowed]
                    passed = len(disallowed) == 0
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=passed,
                            detail=f"All {len(vals)} values are allowed"
                            if passed
                            else f"{len(disallowed)} values not in allowed: {disallowed[:5]}",
                        )
                    )

            elif check == "mapping_applied":
                col = defn.get("column", "")
                mapping = defn.get("mapping", {})
                if col not in target_df.columns:
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=False,
                            detail=f"Column '{col}' does not exist",
                        )
                    )
                else:
                    vals = target_df[col].drop_nulls().to_list()
                    # mapping keys are the pre-mapping variants: none may remain.
                    unmapped = [x for x in vals if x in mapping]
                    passed = len(unmapped) == 0
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=passed,
                            detail=f"All {len(vals)} values mapped"
                            if passed
                            else f"{len(unmapped)} unmapped variants remain: {unmapped[:5]}",
                        )
                    )

            elif check == "mapping_applied":
                col = defn.get("column", "")
                mapping = defn.get("mapping", {})
                if col not in target_df.columns:
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=False,
                            detail=f"Column '{col}' does not exist",
                        )
                    )
                else:
                    vals = target_df[col].drop_nulls().to_list()
                    # mapping keys are the pre-mapping variants: none may remain.
                    unmapped = [x for x in vals if x in mapping]
                    passed = len(unmapped) == 0
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=passed,
                            detail=f"All {len(vals)} values mapped"
                            if passed
                            else f"{len(unmapped)} unmapped variants remain: {unmapped[:5]}",
                        )
                    )

            elif check == "dtype_is":
                col = defn.get("column", "")
                expected_dtype = defn.get("dtype", "")
                if col not in target_df.columns:
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=False,
                            detail=f"Column '{col}' does not exist",
                        )
                    )
                else:
                    actual_dt = str(target_df[col].dtype)
                    try:
                        exp_pl_dt = str_to_dtype(expected_dtype)
                        passed = target_df[col].dtype == exp_pl_dt
                    except Exception:
                        passed = actual_dt.lower() == expected_dtype.lower()
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=passed,
                            detail=(
                                f"Column '{col}' dtype is {actual_dt} "
                                f"(expected {expected_dtype})"
                            ),
                        )
                    )

            elif check == "column_absent":
                col = defn.get("column", "")
                passed = col not in target_df.columns
                results.append(
                    TestResult(
                        name=case.name,
                        passed=passed,
                        detail=f"Column '{col}' is absent"
                        if passed
                        else f"Column '{col}' is present",
                    )
                )

            elif check == "sum_equals":
                col = defn.get("column", "")
                exp_sum = float(defn.get("expected", 0.0))
                tol = float(defn.get("tolerance", 1e-4))
                if col not in target_df.columns:
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=False,
                            detail=f"Column '{col}' does not exist",
                        )
                    )
                else:
                    try:
                        actual_sum = float(target_df[col].sum() or 0.0)
                        passed = abs(actual_sum - exp_sum) <= tol
                        results.append(
                            TestResult(
                                name=case.name,
                                passed=passed,
                                detail=f"Sum of '{col}' is {actual_sum} (expected {exp_sum})",
                            )
                        )
                    except Exception as exc:
                        results.append(
                            TestResult(
                                name=case.name,
                                passed=False,
                                detail=f"Sum check failed with error: {exc}",
                            )
                        )

            elif check == "arithmetic_holds":
                left = defn.get("left", "")
                right = defn.get("right", "")
                tol = float(defn.get("tolerance", 1e-4))
                if left not in target_df.columns or right not in target_df.columns:
                    results.append(
                        TestResult(
                            name=case.name,
                            passed=False,
                            detail=f"Column '{left}' or '{right}' does not exist",
                        )
                    )
                else:
                    try:
                        diff = (
                            target_df[left].cast(pl.Float64) - target_df[right].cast(pl.Float64)
                        ).abs()
                        max_diff = diff.max()
                        passed = max_diff is not None and max_diff <= tol
                        results.append(
                            TestResult(
                                name=case.name,
                                passed=bool(passed),
                                detail=f"Max diff between '{left}' and '{right}' is {max_diff}",
                            )
                        )
                    except Exception as exc:
                        results.append(
                            TestResult(
                                name=case.name,
                                passed=False,
                                detail=f"Arithmetic check failed with error: {exc}",
                            )
                        )

            else:
                results.append(
                    TestResult(
                        name=case.name,
                        passed=False,
                        detail=f"unknown check: {check}",
                    )
                )

        except Exception as exc:
            results.append(
                TestResult(
                    name=case.name,
                    passed=False,
                    detail=f"Check execution error: {exc}",
                )
            )

    return results


def export_pytest(cases: list[TestCase], path: str | Path) -> None:
    """Export test cases as a standalone pytest file.

    Loads data via user-provided load_table(name) in conftest.
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        '"""Auto-generated pytest suite for data pipeline validation.',
        "",
        "Requires load_table(name: str) -> pl.DataFrame helper provided in conftest.py.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import pytest",
        "import polars as pl",
        "from conftest import load_table",
        "",
    ]

    for idx, case in enumerate(cases):
        defn = case.definition
        check = defn.get("check")
        table_name = defn.get("table", "main")
        fn_name = re.sub(r"[^a-zA-Z0-9_]", "_", case.name)
        if not fn_name.startswith("test_"):
            fn_name = f"test_{fn_name}"
        fn_name = f"{fn_name}_{idx}"

        lines.append(f"def {fn_name}():")
        lines.append(f'    """Test case: {case.name} ({case.type})"""')
        lines.append(f'    df = load_table("{table_name}")')

        if check == "no_nulls":
            col = defn.get("column", "")
            lines.append(f'    assert "{col}" in df.columns, "Column {col} missing"')
            lines.append(f'    assert df["{col}"].null_count() == 0, f"Column {col} has nulls"')

        elif check == "unique":
            cols = defn.get("columns", [])
            lines.append(f"    cols = {repr(cols)}")
            lines.append("    for c in cols:")
            lines.append('        assert c in df.columns, f"Column {c} missing"')
            lines.append(
                '    assert df.select(cols).n_unique() == df.height, f"Not unique on {cols}"'
            )

        elif check == "matches_regex":
            col = defn.get("column", "")
            pat = defn.get("pattern", "")
            lines.append(f'    assert "{col}" in df.columns, "Column {col} missing"')
            lines.append(
                f'    assert df["{col}"].drop_nulls().cast(pl.String)'
                f'.str.contains(r"{pat}").all(), "Regex mismatch"'
            )

        elif check == "row_count_equals":
            exp = defn.get("expected")
            lines.append(
                f'    assert df.height == {exp}, f"Expected {exp} rows, got {{df.height}}"'
            )

        elif check == "row_count_gt":
            min_r = defn.get("min", 1)
            lines.append(
                f'    assert df.height >= {min_r}, f"Expected >= {min_r} rows, got {{df.height}}"'
            )

        elif check == "values_in":
            col = defn.get("column", "")
            allowed = sorted(list(defn.get("allowed", [])))
            lines.append(f'    assert "{col}" in df.columns, "Column {col} missing"')
            lines.append(f"    allowed = set({repr(allowed)})")
            lines.append(f'    actual = set(df["{col}"].drop_nulls().to_list())')
            lines.append(
                '    assert actual.issubset(allowed), f"Disallowed values: {actual - allowed}"'
            )

        elif check == "mapping_applied":
            col = defn.get("column", "")
            mapping = defn.get("mapping", {})
            lines.append(f'    assert "{col}" in df.columns, "Column {col} missing"')
            lines.append(f"    mapping = {repr(mapping)}")
            lines.append(f'    vals = df["{col}"].drop_nulls().to_list()')
            lines.append("    unmapped = [x for x in vals if x in mapping]")
            lines.append('    assert not unmapped, f"Unmapped variants remain: {unmapped[:5]}"')

        elif check == "dtype_is":
            col = defn.get("column", "")
            exp_dt = defn.get("dtype", "")
            lines.append(f'    assert "{col}" in df.columns, "Column {col} missing"')
            lines.append(
                f'    assert "{exp_dt}".lower() in str(df["{col}"].dtype).lower(), "Dtype mismatch"'
            )

        elif check == "column_absent":
            col = defn.get("column", "")
            lines.append(f'    assert "{col}" not in df.columns, f"Column {col} should be absent"')

        elif check == "sum_equals":
            col = defn.get("column", "")
            exp_sum = defn.get("expected", 0.0)
            tol = defn.get("tolerance", 1e-4)
            lines.append(f'    assert "{col}" in df.columns, "Column {col} missing"')
            lines.append(f'    actual_sum = float(df["{col}"].sum() or 0.0)')
            lines.append(
                f'    assert abs(actual_sum - {exp_sum}) <= {tol}, f"Sum mismatch: {{actual_sum}}"'
            )

        elif check == "arithmetic_holds":
            left = defn.get("left", "")
            right = defn.get("right", "")
            tol = defn.get("tolerance", 1e-4)
            lines.append(f'    assert "{left}" in df.columns and "{right}" in df.columns')
            lines.append(
                f'    diff = (df["{left}"].cast(pl.Float64) - '
                f'df["{right}"].cast(pl.Float64)).abs().max()'
            )
            lines.append(
                f'    assert diff is not None and diff <= {tol}, f"Arithmetic breach: {{diff}}"'
            )

        else:
            lines.append("    pytest.fail(f'Unknown check: {check}')")

        lines.append("")

    file_path.write_text("\n".join(lines), encoding="utf-8")
