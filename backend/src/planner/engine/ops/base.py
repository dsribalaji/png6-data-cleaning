"""Base definitions and interfaces for data transformation operations.

Pure data logic - no FastAPI/DB imports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, ClassVar

import polars as pl
from dateutil import parser as date_parser


@dataclass
class LossEstimate:
    op: str
    rows_affected: int
    columns_affected: int
    cells_affected: int
    cells_affected_pct: float
    estimated_loss: float  # estimated_loss in 0..1


@dataclass
class InverseOp:
    # op in {"restore_cells", "restore_nulls", "restore_column", "drop_columns", "restore_rows"}
    op: str
    parameters: dict[str, Any]


class Operation(ABC):
    name: ClassVar[str]

    @abstractmethod
    def validate(self, params: dict[str, Any], schema: dict[str, str]) -> None:
        """Validate parameters against current schema (column -> dtype string).

        Raise ValueError with a clear message on bad params.
        """
        ...

    @abstractmethod
    def apply(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
        """Apply operation on DataFrame."""
        ...

    @abstractmethod
    def inverse(
        self, before: pl.DataFrame, after: pl.DataFrame, params: dict[str, Any]
    ) -> InverseOp:
        """Compute the InverseOp that reverses the operation."""
        ...

    @abstractmethod
    def estimate_loss(self, df: pl.DataFrame, params: dict[str, Any]) -> LossEstimate:
        """Estimate data loss resulting from applying this operation."""
        ...

    def extract_tables(
        self, df: pl.DataFrame, params: dict[str, Any]
    ) -> dict[str, pl.DataFrame]:
        """Extract child tables if any (e.g. expand_nested). Default empty dict."""
        return {}


def dtype_to_str(dtype: pl.DataType | type[pl.DataType]) -> str:
    """Return string representation of a polars DataType."""
    return str(dtype)


def str_to_dtype(s: str) -> pl.DataType:
    """Map String/Int64/Float64/Boolean/Date/Datetime; raise ValueError on unknown."""
    s_clean = s.strip()
    lower = s_clean.lower()
    if lower in ("string", "str", "utf8"):
        return pl.String
    if lower in ("int64", "i64", "int"):
        return pl.Int64
    if lower in ("int32", "i32"):
        return pl.Int32
    if lower in ("float64", "f64", "float"):
        return pl.Float64
    if lower in ("float32", "f32"):
        return pl.Float32
    if lower in ("boolean", "bool"):
        return pl.Boolean
    if lower in ("date",):
        return pl.Date
    if lower.startswith("datetime"):
        return pl.Datetime
    if hasattr(pl, s_clean):
        attr = getattr(pl, s_clean)
        if isinstance(attr, pl.DataType) or (
            isinstance(attr, type) and issubclass(attr, pl.DataType)
        ):
            return attr
    raise ValueError(f"Unknown or unsupported dtype: {s}")


def to_jsonable(v: Any) -> Any:
    """Convert value to JSON-serializable representation.

    None -> None, date/datetime -> isoformat, JSON scalar -> as-is, else str(v).
    """
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (bool, int, float, str)):
        return v
    return str(v)


def from_jsonable(v: Any, dtype_str: str) -> Any:
    """Convert JSON-serializable value back to Python/Polars-compatible type."""
    if v is None:
        return None
    ds = dtype_str.lower()
    if "date" in ds and "time" not in ds:
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        return date_parser.parse(str(v)).date()
    if "datetime" in ds:
        if isinstance(v, datetime):
            return v
        return date_parser.parse(str(v))
    if "int" in ds:
        return int(v)
    if "float" in ds:
        return float(v)
    if "bool" in ds:
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)
    if "str" in ds or "utf8" in ds:
        return str(v)
    return v


def frame_equal(a: pl.DataFrame, b: pl.DataFrame) -> bool:
    """Compare two DataFrames for exact equality.

    Same shape, same column order, same dtypes, all values equal with null==null
    and NaN treated as null via fill_nan(None).
    """
    if a.shape != b.shape:
        return False
    if a.columns != b.columns:
        return False
    if a.schema != b.schema:
        return False
    return a.fill_nan(None).equals(b.fill_nan(None))


def apply_inverse(df: pl.DataFrame, inverse: InverseOp) -> pl.DataFrame:
    """Execute restore_cells / restore_nulls / restore_column / drop_columns / restore_rows."""
    op = inverse.op
    p = inverse.parameters

    if op == "restore_cells":
        column = p["column"]
        # An op that renamed the column (expand_nested: col -> col_count) undoes it here.
        if p.get("rename_from") in df.columns and column not in df.columns:
            df = df.rename({p["rename_from"]: column})
        rows = p["rows"]
        values = p["values"]
        dtype_str = p.get("dtype")
        target_dtype = str_to_dtype(dtype_str) if dtype_str else df[column].dtype

        if df[column].dtype != target_dtype:
            cur_vals = [
                from_jsonable(to_jsonable(x), dtype_str or str(target_dtype))
                for x in df[column].to_list()
            ]
        else:
            cur_vals = df[column].to_list()

        for r, v in zip(rows, values):
            cur_vals[r] = from_jsonable(v, dtype_str or str(target_dtype))

        series = pl.Series(column, cur_vals, dtype=target_dtype)
        return df.with_columns(series)

    elif op == "restore_nulls":
        column = p["column"]
        rows = p["rows"]
        dtype_str = p.get("dtype")
        target_dtype = str_to_dtype(dtype_str) if dtype_str else df[column].dtype

        cur_vals = df[column].to_list()
        for r in rows:
            cur_vals[r] = None

        series = pl.Series(column, cur_vals, dtype=target_dtype)
        return df.with_columns(series)

    elif op == "restore_column":
        name = p["name"]
        values = p["values"]
        dtype_str = p["dtype"]
        position = p["position"]
        target_dtype = str_to_dtype(dtype_str)

        vals = [from_jsonable(v, dtype_str) for v in values]
        series = pl.Series(name, vals, dtype=target_dtype)
        pos = min(max(0, position), len(df.columns))
        return df.insert_column(pos, series)

    elif op == "drop_columns":
        columns = p["columns"]
        existing = [c for c in columns if c in df.columns]
        if existing:
            return df.drop(existing)
        return df

    elif op == "restore_rows":
        rows_data = p["rows"]
        dtypes = p["dtypes"]
        columns = p["columns"]

        total_rows = len(df) + len(rows_data)
        dropped_by_pos = {r["position"]: r["values"] for r in rows_data}
        df_iter = iter(df.iter_rows(named=True))

        full_rows = []
        for i in range(total_rows):
            if i in dropped_by_pos:
                row_dict = {
                    c: from_jsonable(dropped_by_pos[i].get(c), dtypes.get(c, "String"))
                    for c in columns
                }
                full_rows.append(row_dict)
            else:
                full_rows.append(next(df_iter))

        schema = {c: str_to_dtype(dtypes[c]) for c in columns}
        return pl.DataFrame(full_rows, schema=schema)

    else:
        raise ValueError(f"Unknown inverse op: {op}")


class _OpsDict(dict):
    def __init__(self) -> None:
        super().__init__()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._loaded = True
            from planner.engine.ops.derive import (
                DeriveColumnOperation,
                ExpandNestedOperation,
                StandardiseFormatOperation,
            )
            from planner.engine.ops.structure import (
                CastTypeOperation,
                DeduplicateOperation,
                DropColumnOperation,
            )
            from planner.engine.ops.values import FillMissingOperation, ReplaceValueOperation

            self.update(
                {
                    "replace_value": ReplaceValueOperation(),
                    "fill_missing": FillMissingOperation(),
                    "drop_column": DropColumnOperation(),
                    "cast_type": CastTypeOperation(),
                    "deduplicate": DeduplicateOperation(),
                    "derive_column": DeriveColumnOperation(),
                    "expand_nested": ExpandNestedOperation(),
                    "standardise_format": StandardiseFormatOperation(),
                }
            )

    def __getitem__(self, key: str) -> Operation:
        self._ensure_loaded()
        return super().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        self._ensure_loaded()
        return super().__contains__(key)

    def get(self, key: str, default: Any = None) -> Any:
        self._ensure_loaded()
        return super().get(key, default)

    def __iter__(self):
        self._ensure_loaded()
        return super().__iter__()

    def __len__(self) -> int:
        self._ensure_loaded()
        return super().__len__()

    def items(self):
        self._ensure_loaded()
        return super().items()

    def values(self):
        self._ensure_loaded()
        return super().values()

    def keys(self):
        self._ensure_loaded()
        return super().keys()


OPS: dict[str, Operation] = _OpsDict()
