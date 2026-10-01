"""SQLAlchemy models for the execution module (schema "execution", Backend.md)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from planner.core.db import Base


class PipelineVersion(Base):
    """Snapshot version produced by executing plan steps."""

    __tablename__ = "pipeline_versions"
    __table_args__ = (
        UniqueConstraint("plan_id", "version_no"),
        {"schema": "execution"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("planning.plan_steps.id"), nullable=True
    )
    snapshot_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    inverse_operation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    executed_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RollbackRow(Base):
    """Record of a rollback operation reverting a plan to an earlier version."""

    __tablename__ = "rollbacks"
    __table_args__ = ({"schema": "execution"},)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    from_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    to_version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExportRow(Base):
    """Record of an exported dataset or pipeline definition."""

    __tablename__ = "exports"
    __table_args__ = (
        CheckConstraint(
            "format IN ('xlsx', 'csv', 'pipeline')",
            name="ck_exports_format",
        ),
        {"schema": "execution"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    exported_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
