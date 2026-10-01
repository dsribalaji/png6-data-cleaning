"""SQLAlchemy models for the validation module (schema "validation", Backend.md)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from planner.core.db import Base


class TestCaseRow(Base):
    """Specification of a test case generated for a plan."""

    __test__ = False
    __tablename__ = "test_cases"
    __table_args__ = (
        CheckConstraint("type IN ('unit', 'integration')", name="ck_test_cases_type"),
        {"schema": "validation"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    target_step_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TestRunRow(Base):
    """Execution result of a test case run in before or after phase."""

    __test__ = False
    __tablename__ = "test_runs"
    __table_args__ = (
        CheckConstraint("phase IN ('before', 'after')", name="ck_test_runs_phase"),
        CheckConstraint("result IN ('passed', 'failed', 'error')", name="ck_test_runs_result"),
        {"schema": "validation"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    test_case_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("validation.test_cases.id"), index=True, nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReconciliationRow(Base):
    """Reconciliation check comparing source invariants to transformed output."""

    __tablename__ = "reconciliations"
    __table_args__ = ({"schema": "validation"},)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    check_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_value: Mapped[str] = mapped_column(Text, nullable=False)
    output_value: Mapped[str] = mapped_column(Text, nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
