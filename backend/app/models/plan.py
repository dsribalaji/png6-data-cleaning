"""Cleaning plan, inferred rules, and step loss estimation database models."""

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk


class InferredRule(Base, UUIDPk):
    """Inferred cleaning rule derived from profiling evidence.

    FR-013 to FR-020: Level-2 deterministic only.
    Level-3 supports AI rule inference via LiteLLM.
    """

    __tablename__ = "inferred_rules"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False, index=True
    )
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class Plan(Base, UUIDPk):
    """Cleaning plan for a dataset.

    FR-027: Status tracks the plan lifecycle:
    draft -> approved -> executing -> done -> rolled_back.
    """

    __tablename__ = "plans"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False, index=True
    )
    # Status: draft / approved / executing / done / rolled_back (FR-027)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class PlanStep(Base, UUIDPk):
    """Individual transformation step within a plan.

    FR-022: op_type must be one of the 8 allowed values:
    - replace_value
    - fill_missing
    - drop_column
    - cast_type
    - derive_column
    - expand_nested
    - deduplicate
    - standardise_format
    """

    __tablename__ = "plan_steps"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    # FR-022 allowed values: replace_value, fill_missing, drop_column, cast_type, derive_column, expand_nested, deduplicate, standardise_format
    op_type: Mapped[str] = mapped_column(String(50), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # Status: proposed / approved / rejected / held / executed
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="proposed")


class LossEstimate(Base, UUIDPk):
    """Pre-execution loss impact estimate for a plan step.

    PROPOSED (contract §6, P3): 5% loss limit threshold.
    held_for_approval is set True when loss_pct exceeds the threshold.
    """

    __tablename__ = "loss_estimates"

    plan_step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_steps.id"), unique=True, nullable=False, index=True
    )
    rows_affected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cols_affected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cells_affected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    loss_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # PROPOSED (contract §6, P3): 5% threshold triggers held_for_approval
    held_for_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
