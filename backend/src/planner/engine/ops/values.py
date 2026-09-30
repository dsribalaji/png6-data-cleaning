"""Value transformation operations: replace_value and fill_missing.

Pure data logic - no FastAPI/DB imports.
"""

from __future__ import annotations

from typing import Any, ClassVar
import polars as pl

from planner.engine.ops.base import (
    InverseOp,
    LossEstimate,
    Operation,
    dtype_to_str,
    to_jsonable,
)


class ReplaceValueOperation(Operation):
    name: ClassVar[str] = "replace_value"

    def validate(self, params: dict[str, Any], schema: dict[str, str]) -> None:
        if "column" not in params or not isinstance(params["column"], str):
            raise ValueError("Parameter 'column' must be a string")
        column = params["column"]
        if column not in schema:
            raise ValueError(f"Column '{column}' does not exist in schema")
        col_type = schema[column]
        if col_type != "String" and col_type.lower() not in ("string", "str"):
            raise ValueError(f"Column '{column}' must be String, got {col_type}")

        mapping = params.get("mapping")
        if not isinstance(mapping, dict) or len(mapping) == 0:
            raise ValueError("Parameter 'mapping' must be a non-empty dictionary")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
            raise ValueError("Parameter 'mapping' must map strings to strings")

    def apply(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
        column = params["column"]
        mapping = params["mapping"]
        return df.with_columns(pl.col(column).replace_strict(mapping, default=pl.col(column)))

    def inverse(
        self, before: pl.DataFrame, after: pl.DataFrame, params: dict[str, Any]
    ) -> InverseOp:
        column = params["column"]
        before_vals = before[column].to_list()
        after_vals = after[column].to_list()

        rows: list[int] = []
        values: list[Any] = []
        for i, (b, a) in enumerate(zip(before_vals, after_vals)):
            if b != a:
                rows.append(i)
                values.append(to_jsonable(b))

        return InverseOp(
            op="restore_cells",
            parameters={
                "column": column,
                "rows": rows,
                "values": values,
                "dtype": dtype_to_str(before[column].dtype),
            },
        )

    def estimate_loss(self, df: pl.DataFrame, params: dict[str, Any]) -> LossEstimate:
        column = params["column"]
        mapping = params.get("mapping", {})
        total_cells = df.height * df.width

        changed = 0
        if column in df.columns:
            s = df[column].to_list()
            changed = sum(1 for x in s if x in mapping and mapping[x] != x)

        pct = (changed / total_cells) if total_cells > 0 else 0.0
        return LossEstimate(
            op=self.name,
            rows_affected=changed,
            columns_affected=1 if total_cells > 0 else 0,
            cells_affected=changed,
            cells_affected_pct=pct,
            estimated_loss=pct,
        )


class FillMissingOperation(Operation):
    name: ClassVar[str] = "fill_missing"

    def validate(self, params: dict[str, Any], schema: dict[str, str]) -> None:
        if "column" not in params or not isinstance(params["column"], str):
            raise ValueError("Parameter 'column' must be a string")
        column = params["column"]
        if column not in schema:
            raise ValueError(f"Column '{column}' does not exist in schema")
        if "value" not in params:
            raise ValueError("Parameter 'value' is required")
        val = params["value"]
        if not isinstance(val, (str, int, float, bool)):
            raise ValueError("Parameter 'value' must be str, int, float, or bool")

    def apply(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
        column = params["column"]
        val = params["value"]
        col_dtype = df[column].dtype

        if col_dtype == pl.String and not isinstance(val, str):
            fill_val: Any = str(val)
        elif col_dtype in (pl.Int64, pl.Int32) and isinstance(val, (int, float)):
            fill_val = int(val)
        elif col_dtype in (pl.Float64, pl.Float32) and isinstance(val, (int, float)):
            fill_val = float(val)
        elif col_dtype == pl.Boolean:
            fill_val = bool(val)
        else:
            fill_val = val

        return df.with_columns(pl.col(column).fill_null(fill_val))

    def inverse(
        self, before: pl.DataFrame, after: pl.DataFrame, params: dict[str, Any]
    ) -> InverseOp:
        column = params["column"]
        before_vals = before[column].to_list()
        rows = [i for i, b in enumerate(before_vals) if b is None]

        return InverseOp(
            op="restore_nulls",
            parameters={
                "column": column,
                "rows": rows,
                "dtype": dtype_to_str(before[column].dtype),
            },
        )

    def estimate_loss(self, df: pl.DataFrame, params: dict[str, Any]) -> LossEstimate:
        column = params["column"]
        total_cells = df.height * df.width

        nulls_filled = 0
        if column in df.columns:
            nulls_filled = df[column].null_count()

        pct = (nulls_filled / total_cells) if total_cells > 0 else 0.0
        return LossEstimate(
            op=self.name,
            rows_affected=nulls_filled,
            columns_affected=1 if total_cells > 0 else 0,
            cells_affected=nulls_filled,
            cells_affected_pct=pct,
            estimated_loss=pct,
        )
