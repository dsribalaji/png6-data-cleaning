"""SQLAlchemy models for the planning module (schema 'planning', Backend.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from planner.core.db import Base


class Plan(Base):
    """Represents a data cleaning plan composed of ordered operations."""

    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'in_review', 'approved', 'rejected', 'superseded')",
            name="ck_plans_status",
        ),
        {"schema": "planning"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    status: Mapped[str] = mapped_column(String(50), default="proposed")
    total_estimated_loss: Mapped[float] = mapped_column(Numeric(6, 3), default=0.0)
    loss_threshold: Mapped[float] = mapped_column(Numeric(6, 3), default=0.05)
    approved_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlanStep(Base):
    """An individual cleaning step in a plan."""

    __tablename__ = "plan_steps"
    __table_args__ = (
        UniqueConstraint("plan_id", "step_no", name="uq_plan_steps_plan_id_step_no"),
        CheckConstraint(
            "operation IN ('replace_value', 'fill_missing', 'drop_column', 'cast_type', "
            "'derive_column', 'expand_nested', 'deduplicate', 'standardise_format')",
            name="ck_plan_steps_operation",
        ),
        CheckConstraint(
            "decision IN ('pending', 'accepted', 'edited', 'rejected')",
            name="ck_plan_steps_decision",
        ),
        {"schema": "planning"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    step_no: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(50))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    rationale: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2))
    decision: Mapped[str] = mapped_column(String(20), default="pending")
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LossEstimateRow(Base):
    """Estimated loss breakdown for a plan step."""

    __tablename__ = "loss_estimates"
    __table_args__ = {"schema": "planning"}

    step_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("planning.plan_steps.id"), primary_key=True
    )
    rows_affected: Mapped[int] = mapped_column(Integer)
    columns_affected: Mapped[int] = mapped_column(Integer)
    cells_affected: Mapped[int] = mapped_column(Integer)
    estimated_loss: Mapped[float] = mapped_column(Numeric(6, 3))
