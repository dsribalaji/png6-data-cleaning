"""Pydantic schemas for the profiling module (camelCase on wire, Backend.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class CamelModel(BaseModel):
    """Base model enforcing camelCase serialization."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class ColumnProfileOut(CamelModel):
    name: str
    ordinal: int
    physical_type: str
    semantic_type: str
    null_count: int
    null_pct: float
    distinct_count: int
    min_value: str | None = None
    max_value: str | None = None
    mean_value: float | None = None
    flags: list[str] = Field(default_factory=list)


class FlaggedCellOut(CamelModel):
    column: str
    row: int
    preview: str
    reason: str


class ProfileResponse(CamelModel):
    dataset_id: UUID
    row_count: int
    column_count: int
    columns: list[ColumnProfileOut]
    issues: list[str] = Field(default_factory=list)
    profiled_at: datetime
    # Level 3 B2: "used" | "off" | "failed" (None until rules are inferred) and why.
    ai_status: str | None = None
    ai_message: str | None = None
    # FR-045: cells that look like instructions to an AI model; never sent to one.
    flagged_cells: list[FlaggedCellOut] = Field(default_factory=list)


class RuleOut(CamelModel):
    id: UUID
    rule_type: str
    columns: list[str]
    expression: dict[str, Any]
    confidence: float
    evidence: dict[str, Any] = Field(default_factory=dict)
    source: str


class RulesResponse(CamelModel):
    dataset_id: UUID
    items: list[RuleOut]
    total: int
