"""SQLAlchemy models for the evaluation module (schema "evaluation", Backend.md)."""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from planner.core.db import Base


def _uuid7() -> uuid.UUID:
    """Generate an RFC 9562 UUIDv7 (48-bit unix-ms timestamp, ver 0111, variant 10)."""
    unix_ts_ms = int(time.time() * 1000)
    val = (
        (unix_ts_ms << 80)
        | (0x7 << 76)
        | (secrets.randbits(12) << 64)
        | (0x2 << 62)
        | secrets.randbits(62)
    )
    return uuid.UUID(int=val)


class BenchmarkSet(Base):
    """evaluation.benchmark_sets - collection of fixture datasets for evaluation."""

    __tablename__ = "benchmark_sets"
    __table_args__ = {"schema": "evaluation"}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid7)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    object_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class EvaluationRun(Base):
    """evaluation.evaluation_runs - an execution of a benchmark set."""

    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','succeeded','failed')",
            name="status",
        ),
        {"schema": "evaluation"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid7)
    benchmark_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("evaluation.benchmark_sets.id"), nullable=False
    )
    model_config_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("model_config.model_configs.id"), nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    scores: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, default=None)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
