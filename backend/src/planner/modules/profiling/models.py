"""SQLAlchemy models for the profiling module (schema 'profiling', Backend.md)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from planner.core.db import Base


class ColumnProfileRow(Base):
    """Stores per-column profile metrics for a dataset."""

    __tablename__ = "column_profiles"
    __table_args__: ClassVar[dict] = {"schema": "profiling"}

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    column_name: Mapped[str] = mapped_column(String(255))
    ordinal: Mapped[int] = mapped_column(Integer)
    physical_type: Mapped[str] = mapped_column(String(100))
    semantic_type: Mapped[str] = mapped_column(String(100))
    null_count: Mapped[int] = mapped_column(Integer)
    null_pct: Mapped[float] = mapped_column(Float)
    distinct_count: Mapped[int] = mapped_column(Integer)
    min_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    mean_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InferredRuleRow(Base):
    """Stores inferred cleaning/semantic rules for a dataset."""

    __tablename__ = "inferred_rules"
    __table_args__ = (
        CheckConstraint(
            "rule_type IN ('entity_group', 'arithmetic', 'primary_key', "
            "'one_to_many', 'semantic_type', 'cross_field_fill', 'all_null')",
            name="ck_inferred_rules_rule_type",
        ),
        {"schema": "profiling"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    rule_type: Mapped[str] = mapped_column(String(50))
    columns: Mapped[list[str]] = mapped_column(JSON)
    expression: Mapped[dict[str, Any]] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2))
    evidence_rows: Mapped[Any] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(50), default="deterministic")
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProfileRun(Base):
    """Stores dataset-level profile summary metrics."""

    __tablename__ = "profile_runs"
    __table_args__: ClassVar[dict] = {"schema": "profiling"}

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, unique=True, index=True)
    row_count: Mapped[int] = mapped_column(Integer)
    column_count: Mapped[int] = mapped_column(Integer)
    issues: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Level 3 B2: "used" | "off" | "failed" for AI rule inference, with the reason.
    ai_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # FR-045: cells the injection guard flagged ({column, row, preview, pattern}).
    flagged_cells: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    profiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


ProfileRunRow = ProfileRun
