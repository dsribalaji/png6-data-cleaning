"""SQLAlchemy models for the datasets module (schema "datasets", Backend.md)."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from planner.core.db import Base, schema_for, uuid7

SCHEMA = schema_for("datasets")


def _fk(table_col: str) -> str:
    """Build schema-qualified foreign key string for portable Postgres/SQLite support."""
    return f"{SCHEMA + '.' if SCHEMA else ''}{table_col}"


class Dataset(Base):
    """datasets.datasets - System of record for uploaded and polled datasets."""

    __tablename__ = "datasets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="profiling")
    raw_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Parquet written by engine ingest; read by profiling/execution.
    # Added in integration 2026-09-30 (was referenced but never modelled).
    ingested_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # uploaded_by: plain UUID without FK constraint because users module is in a separate
    # schema ('users'), and cross-schema foreign keys break on SQLite and between isolated modules.
    uploaded_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("source IN ('upload', 'n8n_folder')", name="ck_datasets_source"),
        CheckConstraint(
            "status IN ('profiling', 'profiled', 'plan_ready', 'approved', 'executed', "
            "'tests_failed', 'rolled_back', 'failed')",
            name="ck_datasets_status",
        ),
        {"schema": SCHEMA},
    )
    __mapper_args__: ClassVar[dict] = {"version_id_col": version}

    quarantine_records: Mapped[list[QuarantineRecord]] = relationship(
        "QuarantineRecord",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="QuarantineRecord.created_at",
    )
    jobs: Mapped[list[Job]] = relationship(
        "Job",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="Job.created_at",
    )


class QuarantineRecord(Base):
    """datasets.quarantine_records - Structural pre-check and malformed row failures."""

    __tablename__ = "quarantine_records"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(_fk("datasets.id"), ondelete="CASCADE"),
        nullable=False,
    )
    row_ref: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = ({"schema": SCHEMA},)

    dataset: Mapped[Dataset] = relationship("Dataset", back_populates="quarantine_records")


class Job(Base):
    """datasets.jobs - Background execution units for dataset lifecycle."""

    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(_fk("datasets.id"), ondelete="CASCADE"),
        nullable=False,
    )
    # plan_id: plain UUID without FK constraint because planning module owns plans
    plan_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_jobs_status",
        ),
        {"schema": SCHEMA},
    )

    dataset: Mapped[Dataset] = relationship("Dataset", back_populates="jobs")
