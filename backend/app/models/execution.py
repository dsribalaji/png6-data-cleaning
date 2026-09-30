"""Pipeline execution versioning, test case, and test run database models."""

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk


class PipelineVersion(Base, UUIDPk):
    """Pipeline execution version tracking for deterministic rollback.

    FR-032: Each executed step is recorded with its inverse operations to
    enable byte-for-byte rollback (FR-033, FR-034).
    """

    __tablename__ = "pipeline_versions"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # FR-032: each executed step recorded with its inverse operations
    inverse_ops: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class TestCase(Base, UUIDPk):
    """Generated test case for plan verification.

    FR-039 / FR-040: Unit tests per step and integration tests for schema
    compliance and business rule integrity.
    """

    __tablename__ = "test_cases"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # kind: unit / integration (FR-039 / FR-040)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class TestRun(Base, UUIDPk):
    """Test execution result record.

    FR-041: Tests run pre AND post execution.
    FR-043: Export withheld when any test run fails.
    """

    __tablename__ = "test_runs"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False, index=True
    )
    # phase: pre / post (FR-041)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # FR-043: export withheld when any run fails
    ran_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
