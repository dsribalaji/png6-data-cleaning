"""Structural transformation operations: drop_column, cast_type, and deduplicate.

Pure data logic - no FastAPI/DB imports.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar

import polars as pl
from dateutil import parser as date_parser

from planner.engine.ops.base import (
    InverseOp,
    LossEstimate,
    Operation,
    dtype_to_str,
    to_jsonable,
)


class DropColumnOperation(Operation):
    name: ClassVar[str] = "drop_column"

    def validate(self, params: dict[str, Any], schema: dict[str, str]) -> None:
        if "column" not in params or not isinstance(params["column"], str):
            raise ValueError("Parameter 'column' must be a string")
        column = params["column"]
        if column not in schema:
            raise ValueError(f"Column '{column}' does not exist in schema")

    def apply(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
        column = params["column"]
        return df.drop(column)

    def inverse(
        self, before: pl.DataFrame, after: pl.DataFrame, params: dict[str, Any]
    ) -> InverseOp:
        column = params["column"]
        values = [to_jsonable(v) for v in before[column].to_list()]
        dtype = dtype_to_str(before[column].dtype)
        position = before.columns.index(column)

        return InverseOp(
            op="restore_column",
            parameters={
                "name": column,
                "values": values,
                "dtype": dtype,
                "position": position,
            },
        )

    def estimate_loss(self, df: pl.DataFrame, params: dict[str, Any]) -> LossEstimate:
        # Only non-null values are destroyed; dropping an all-null column loses nothing.
        total_cells = df.height * df.width
        lost = df.height - df[params["column"]].null_count()
        twin = params.get("redundant_with")
        if twin in df.columns and df[params["column"]].equals(df[twin], null_equal=True):
            lost = 0  # values stay recoverable from the identical twin column
        pct = (lost / total_cells) if total_cells > 0 else 0.0
        return LossEstimate(
            op=self.name,
            rows_affected=lost,
            columns_affected=1 if lost else 0,
            cells_affected=df.height,
            cells_affected_pct=(df.height / total_cells) if total_cells else 0.0,
            estimated_loss=pct,
        )


class CastTypeOperation(Operation):
    name: ClassVar[str] = "cast_type"

    def validate(self, params: dict[str, Any], schema: dict[str, str]) -> None:
        if "column" not in params or not isinstance(params["column"], str):
            raise ValueError("Parameter 'column' must be a string")
        column = params["column"]
        if column not in schema:
            raise ValueError(f"Column '{column}' does not exist in schema")

        dtype = params.get("dtype")
        if dtype not in {"float", "int", "string", "date"}:
            raise ValueError(
                f"Parameter 'dtype' must be one of 'float', 'int', 'string', 'date', got '{dtype}'"
            )

    def apply(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
        column = params["column"]
        target_type = params["dtype"]
        strip_chars = params.get("strip_chars", "")

        s = df[column]
        if strip_chars:
            table = str.maketrans("", "", strip_chars)
            stripped_vals = [
                str(x).translate(table) if x is not None else None
                for x in s.to_list()
            ]
            s = pl.Series(column, stripped_vals, dtype=pl.String)

        if target_type == "float":
            casted = s.cast(pl.Float64, strict=False)
        elif target_type == "int":
            if s.dtype == pl.String:
                casted = s.cast(pl.Float64, strict=False).cast(pl.Int64, strict=False)
            else:
                casted = s.cast(pl.Int64, strict=False)
        elif target_type == "string":
            casted = s.cast(pl.String, strict=False)
        elif target_type == "date":
            parsed_dates: list[date | None] = []
            for item in s.to_list():
                if item is None:
                    parsed_dates.append(None)
                elif isinstance(item, (date, datetime)):
                    parsed_dates.append(item.date() if isinstance(item, datetime) else item)
                else:
                    try:
                        parsed_dates.append(date_parser.parse(str(item)).date())
                    except (ValueError, TypeError, OverflowError):
                        parsed_dates.append(None)
            casted = pl.Series(column, parsed_dates, dtype=pl.Date)
        else:
            raise ValueError(f"Unsupported dtype: {target_type}")

        return df.with_columns(casted)

    def inverse(
        self, before: pl.DataFrame, after: pl.DataFrame, params: dict[str, Any]
    ) -> InverseOp:
        column = params["column"]
        dtype_str = dtype_to_str(before[column].dtype)
        rows = list(range(len(before)))
        values = [to_jsonable(v) for v in before[column].to_list()]

        return InverseOp(
            op="restore_cells",
            parameters={
                "column": column,
                "rows": rows,
                "values": values,
                "dtype": dtype_str,
            },
        )

    def estimate_loss(self, df: pl.DataFrame, params: dict[str, Any]) -> LossEstimate:
        column = params["column"]
        total_cells = df.height * df.width

        if column not in df.columns:
            return LossEstimate(self.name, 0, 0, 0, 0.0, 0.0)

        after = self.apply(df, params)
        b_vals = df[column].to_list()
        a_vals = after[column].to_list()
        b_dt = df[column].dtype
        a_dt = after[column].dtype

        changed = 0
        for b, a in zip(b_vals, a_vals):
            if b is None and a is None:
                continue
            if b is None or a is None or b_dt != a_dt or b != a:
                changed += 1

        pct = (changed / total_cells) if total_cells > 0 else 0.0
        return LossEstimate(
            op=self.name,
            rows_affected=changed,
            columns_affected=1 if total_cells > 0 else 0,
            cells_affected=changed,
            cells_affected_pct=pct,
            estimated_loss=pct,
        )


class DeduplicateOperation(Operation):
    name: ClassVar[str] = "deduplicate"

    def validate(self, params: dict[str, Any], schema: dict[str, str]) -> None:
        subset = params.get("subset")
        if subset is not None:
            if not isinstance(subset, list):
                raise ValueError("Parameter 'subset' must be a list of column names or None")
            for col in subset:
                if col not in schema:
                    raise ValueError(f"Column '{col}' in subset does not exist in schema")

    def apply(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
        subset = params.get("subset")
        return df.unique(subset=subset, keep="first", maintain_order=True)

    def inverse(
        self, before: pl.DataFrame, after: pl.DataFrame, params: dict[str, Any]
    ) -> InverseOp:
        subset = params.get("subset")
        actual_subset = subset if subset is not None else before.columns

        before_with_idx = before.with_columns(pl.Series("__orig_row_idx", range(len(before))))
        kept = before_with_idx.unique(subset=actual_subset, keep="first", maintain_order=True)
        kept_indices = set(kept["__orig_row_idx"].to_list())
        dropped_df = before_with_idx.filter(~pl.col("__orig_row_idx").is_in(kept_indices))

        dropped_rows: list[dict[str, Any]] = []
        for row in dropped_df.iter_rows(named=True):
            pos = int(row.pop("__orig_row_idx"))
            dropped_rows.append(
                {"position": pos, "values": {c: to_jsonable(v) for c, v in row.items()}}
            )

        dtypes = {c: dtype_to_str(before[c].dtype) for c in before.columns}
        columns = list(before.columns)

        return InverseOp(
            op="restore_rows",
            parameters={
                "rows": dropped_rows,
                "dtypes": dtypes,
                "columns": columns,
            },
        )

    def estimate_loss(self, df: pl.DataFrame, params: dict[str, Any]) -> LossEstimate:
        after = self.apply(df, params)
        dropped_rows = df.height - after.height
        n_cols = df.width
        cells_affected = dropped_rows * n_cols
        total_cells = df.height * n_cols
        pct = (cells_affected / total_cells) if total_cells > 0 else 0.0

        return LossEstimate(
            op=self.name,
            rows_affected=dropped_rows,
            columns_affected=n_cols if dropped_rows > 0 else 0,
            cells_affected=cells_affected,
            cells_affected_pct=pct,
            estimated_loss=pct,
        )
