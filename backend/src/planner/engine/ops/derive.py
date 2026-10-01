"""Derivation operations: derive_column, expand_nested, and standardise_format.

Pure data logic - no FastAPI/DB imports.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

import polars as pl
from dateutil import parser as date_parser

from planner.engine.nested import looks_nested, parse_nested
from planner.engine.ops.base import (
    InverseOp,
    LossEstimate,
    Operation,
    to_jsonable,
)


class DeriveColumnOperation(Operation):
    name: ClassVar[str] = "derive_column"

    def validate(self, params: dict[str, Any], schema: dict[str, str]) -> None:
        name = params.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("Parameter 'name' must be a non-empty string")

        expr = params.get("expression")
        if not isinstance(expr, dict):
            raise TypeError("Parameter 'expression' must be a dictionary")

        op = expr.get("op")
        if op not in {"add", "subtract", "multiply", "divide"}:
            raise ValueError(
                f"Expression 'op' must be one of 'add', 'subtract', "
                f"'multiply', 'divide', got '{op}'"
            )

        args = expr.get("args")
        if not isinstance(args, list) or len(args) < 2:
            raise ValueError("Expression 'args' must be a list of at least two items")

        for idx, arg in enumerate(args):
            if not isinstance(arg, dict):
                raise TypeError(f"Argument at index {idx} must be a dictionary")
            if "column" in arg:
                col = arg["column"]
                if col not in schema:
                    raise ValueError(
                        f"Column '{col}' referenced in expression does not exist in schema"
                    )
                col_type = schema[col].lower()
                if not any(t in col_type for t in ("int", "float", "decimal", "numeric")):
                    raise ValueError(f"Column '{col}' must be numeric, got {schema[col]}")
            elif "literal" in arg:
                lit = arg["literal"]
                if not isinstance(lit, (int, float)) or isinstance(lit, bool):
                    raise ValueError(f"Literal at index {idx} must be a number, got {type(lit)}")
            else:
                raise ValueError(f"Argument at index {idx} must have 'column' or 'literal'")

    def apply(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
        name = params["name"]
        expr = params["expression"]
        op = expr["op"]
        args = expr["args"]

        cur_expr: pl.Expr | None = None
        for arg in args:
            if "column" in arg:
                term = pl.col(arg["column"]).cast(pl.Float64)
            else:
                term = pl.lit(float(arg["literal"]))

            if cur_expr is None:
                cur_expr = term
            else:
                if op == "add":
                    cur_expr = cur_expr + term
                elif op == "subtract":
                    cur_expr = cur_expr - term
                elif op == "multiply":
                    cur_expr = cur_expr * term
                elif op == "divide":
                    cur_expr = cur_expr / term

        assert cur_expr is not None
        return df.with_columns(cur_expr.alias(name))

    def inverse(
        self, before: pl.DataFrame, after: pl.DataFrame, params: dict[str, Any]
    ) -> InverseOp:
        name = params["name"]
        return InverseOp(op="drop_columns", parameters={"columns": [name]})

    def estimate_loss(self, df: pl.DataFrame, params: dict[str, Any]) -> LossEstimate:
        total_cells = df.height * df.width
        cells_affected = df.height
        pct = (cells_affected / total_cells) if total_cells > 0 else 0.0

        return LossEstimate(
            op=self.name,
            rows_affected=df.height,
            columns_affected=1 if total_cells > 0 else 0,
            cells_affected=cells_affected,
            cells_affected_pct=pct,
            estimated_loss=pct,
        )


class ExpandNestedOperation(Operation):
    name: ClassVar[str] = "expand_nested"

    def _key_column(self, params: dict[str, Any]) -> str:
        # The planner emits {"parent_key": "_row"} when the dataset has no PK.
        # "_row" is a virtual positional key: it is never materialised on the
        # parent frame, only used as the link column in the extracted child table.
        return str(params.get("key_column", params.get("parent_key", "_row")))

    def validate(self, params: dict[str, Any], schema: dict[str, str]) -> None:
        col = params.get("column")
        if not col or not isinstance(col, str):
            raise ValueError("Parameter 'column' must be a non-empty string")
        if col not in schema:
            raise ValueError(f"Column '{col}' does not exist in schema")
        col_type = schema[col].lower()
        if col_type not in ("string", "str", "utf8"):
            raise ValueError(f"Column '{col}' must be String, got {schema[col]}")

        key_col = self._key_column(params)
        if not key_col:
            raise ValueError("Parameter 'key_column' must be a non-empty string")
        if key_col != "_row" and key_col not in schema:
            raise ValueError(f"Key column '{key_col}' does not exist in schema")

        child_table = params.get("child_table")
        if not child_table or not isinstance(child_table, str):
            raise ValueError("Parameter 'child_table' must be a non-empty string")

    @staticmethod
    def _parse_cell(cell: Any) -> list[dict[str, Any]]:
        # Shared parser: strict JSON, Python-style literals, salvaged cut-off lists.
        return parse_nested(cell).items

    @staticmethod
    def count_column(df_columns: list[str], col: str) -> str:
        """The records move to the child table; the parent keeps how many there were,
        under a name that says so ("items" -> "items_count")."""
        name = f"{col}_count"
        return name if name not in df_columns else col

    def apply(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
        col = params["column"]
        counts = [len(self._parse_cell(c)) for c in df[col].to_list()]
        out = df.with_columns(pl.Series(col, counts, dtype=pl.Int64))
        target = self.count_column(df.columns, col)
        return out.rename({col: target}) if target != col else out

    def extract_tables(
        self, df: pl.DataFrame, params: dict[str, Any]
    ) -> dict[str, pl.DataFrame]:
        col = params["column"]
        key_col = self._key_column(params)
        child_table = params["child_table"]

        if col not in df.columns or df[col].dtype != pl.String:
            return {child_table: pl.DataFrame()}

        child_rows: list[dict[str, Any]] = []
        all_item_keys: list[str] = []

        if key_col == "_row" or key_col not in df.columns:
            keys = list(range(df.height))
            link_col = "_row"
        else:
            keys = df[key_col].to_list()
            link_col = key_col
        cells = df[col].to_list()

        for parent_key, cell in zip(keys, cells):
            items = self._parse_cell(cell)
            for it in items:
                for it_k in it:
                    if it_k not in all_item_keys:
                        all_item_keys.append(it_k)
                row_dict = {link_col: parent_key, **it}
                child_rows.append(row_dict)

        if child_rows:
            # Build column-wise so each column's dtype is inferred from ALL rows
            # (row-wise construction only samples the first 100 rows, which breaks
            # when the leading items are all null for a column, e.g. 'description').
            full_keys = [link_col] + [k for k in all_item_keys if k != link_col]
            child_df = pl.DataFrame(
                {k: pl.Series(k, [row.get(k) for row in child_rows], strict=False) for k in full_keys}
            )
        else:
            child_df = pl.DataFrame()

        return {child_table: _coerce_numeric_text(child_df)}

    def inverse(
        self, before: pl.DataFrame, after: pl.DataFrame, params: dict[str, Any]
    ) -> InverseOp:
        col = params["column"]
        rows = list(range(len(before)))
        values = [to_jsonable(v) for v in before[col].to_list()]

        return InverseOp(
            op="restore_cells",
            parameters={
                "column": col,
                "rows": rows,
                "values": values,
                "dtype": "String",
                "rename_from": self.count_column(before.columns, col),
            },
        )

    def estimate_loss(self, df: pl.DataFrame, params: dict[str, Any]) -> LossEstimate:
        # Every cell is rewritten (JSON -> item count), but the content moves to the
        # child table; only non-empty cells that fail to parse are actually lost.
        col = params["column"]
        total_cells = df.height * df.width
        cells = df[col].to_list()
        affected = sum(1 for c in cells if c is not None)
        # Lost: cells nothing could be recovered from, plus cut-off cells (their last,
        # incomplete item is gone). Repaired cells (single quotes) lose nothing.
        lost = sum(
            1 for c in cells if looks_nested(c) and parse_nested(c).status in ("invalid", "partial")
        )
        return LossEstimate(
            op=self.name,
            rows_affected=affected,
            columns_affected=1 if affected else 0,
            cells_affected=affected,
            cells_affected_pct=(affected / total_cells) if total_cells else 0.0,
            estimated_loss=(lost / total_cells) if total_cells else 0.0,
        )


_NUMERIC_TEXT = re.compile(r"^\s*[-+]?\$?\s*(\d{1,3}(,\d{3})+|\d+)?(\.\d+)?\s*$")


def _coerce_numeric_text(df: pl.DataFrame) -> pl.DataFrame:
    """Cast String columns whose every value is numeric text ("$140.00", "4,735.12")
    to Float64 (dollar-text-in-json), rounding binary float artifacts to cents."""
    out = []
    for name in df.columns:
        s = df[name]
        vals = s.drop_nulls().to_list() if s.dtype == pl.String else []
        if vals and all(v.strip() and _NUMERIC_TEXT.match(v) for v in vals):
            nums = s.str.replace_all(r"[\$,\s]", "").cast(pl.Float64)
            if (nums - nums.round(2)).abs().max() < 1e-6:  # float-artifacts
                nums = nums.round(2)
            out.append(nums)
        else:
            out.append(s)
    return pl.DataFrame(out) if out else df


class StandardiseFormatOperation(Operation):
    name: ClassVar[str] = "standardise_format"

    def validate(self, params: dict[str, Any], schema: dict[str, str]) -> None:
        col = params.get("column")
        if not col or not isinstance(col, str):
            raise ValueError("Parameter 'column' must be a non-empty string")
        if col not in schema:
            raise ValueError(f"Column '{col}' does not exist in schema")
        col_type = schema[col].lower()
        if col_type not in ("string", "str", "utf8"):
            raise ValueError(f"Column '{col}' must be String, got {schema[col]}")

        fmt = params.get("format")
        if fmt not in {"iso_date", "lower", "upper", "strip", "title"}:
            raise ValueError(
                f"Format must be one of 'iso_date', 'lower', 'upper', 'strip', 'title', got '{fmt}'"
            )

    def apply(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
        col = params["column"]
        fmt = params["format"]
        raw = df[col].to_list()

        if fmt == "iso_date":
            new_vals: list[str | None] = []
            for item in raw:
                if item is None:
                    new_vals.append(None)
                else:
                    try:
                        new_vals.append(date_parser.parse(str(item)).date().isoformat())
                    except (ValueError, TypeError, OverflowError):
                        new_vals.append(None)
        elif fmt == "lower":
            new_vals = [str(x).lower() if x is not None else None for x in raw]
        elif fmt == "upper":
            new_vals = [str(x).upper() if x is not None else None for x in raw]
        elif fmt == "strip":
            new_vals = [str(x).strip() if x is not None else None for x in raw]
        elif fmt == "title":
            new_vals = [str(x).title() if x is not None else None for x in raw]
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        return df.with_columns(pl.Series(col, new_vals, dtype=pl.String))

    def inverse(
        self, before: pl.DataFrame, after: pl.DataFrame, params: dict[str, Any]
    ) -> InverseOp:
        col = params["column"]
        b_vals = before[col].to_list()
        a_vals = after[col].to_list()

        rows: list[int] = []
        values: list[Any] = []
        for i, (b, a) in enumerate(zip(b_vals, a_vals)):
            if b != a:
                rows.append(i)
                values.append(to_jsonable(b))

        return InverseOp(
            op="restore_cells",
            parameters={
                "column": col,
                "rows": rows,
                "values": values,
                "dtype": "String",
            },
        )

    def estimate_loss(self, df: pl.DataFrame, params: dict[str, Any]) -> LossEstimate:
        after = self.apply(df, params)
        total_cells = df.height * df.width
        col = params["column"]

        b_vals = df[col].to_list()
        a_vals = after[col].to_list()
        changed = sum(1 for b, a in zip(b_vals, a_vals) if b != a)

        pct = (changed / total_cells) if total_cells > 0 else 0.0
        return LossEstimate(
            op=self.name,
            rows_affected=changed,
            columns_affected=1 if total_cells > 0 else 0,
            cells_affected=changed,
            cells_affected_pct=pct,
            estimated_loss=pct,
        )
