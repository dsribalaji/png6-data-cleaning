"""Audit trail and model configuration database models."""

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk


class AuditEvent(Base, UUIDPk):
    """Immutable audit trail event.

    FR-051 / FR-052: Tracks all user and system operations including ingest,
    plan approval, execution, and rollback.
    """

    __tablename__ = "audit_events"

    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ModelConfig(Base, UUIDPk):
    """LLM provider configuration.

    FR-049: Model-agnostic configuration. credential_ref stores a reference/pointer
    only, never the secret key itself.
    """

    __tablename__ = "model_configs"

    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # FR-049: reference only, never the key itself
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
