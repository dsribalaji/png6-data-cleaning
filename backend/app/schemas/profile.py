"""Profiling and quarantine response schemas."""

from typing import Any
import uuid
from pydantic import BaseModel, Field


class ColumnProfileOut(BaseModel):
    """Profiling metrics and issue flags for a single column."""

    name: str = Field(..., description="Column header name")
    dtype: str = Field(..., description="Inferred data type")
    null_count: int = Field(..., description="Count of null or missing values")
    null_pct: float = Field(..., description="Percentage of null values")
    distinct_count: int = Field(..., description="Number of distinct values")
    unique_count: int = Field(..., description="Number of values occurring exactly once")
    stats: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics (min, max, mean)",
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Detected issue flags (e.g. all_null, embedded_json, currency_text, float_artifact)",
    )


class ProfileReportOut(BaseModel):
    """Full profiling report for a dataset."""

    dataset_id: uuid.UUID = Field(..., description="Associated dataset identifier")
    columns: list[ColumnProfileOut] = Field(..., description="Profiling summaries for all columns")
    quarantined_rows: int = Field(..., description="Count of malformed or poisoned quarantined rows")


class QuarantineRecordOut(BaseModel):
    """Quarantine entry details."""

    row_index: int = Field(..., description="Index of the row in the source file")
    reason: str = Field(..., description="Reason the row was quarantined")
