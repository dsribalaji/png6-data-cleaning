"""SQLAlchemy models for the audit module (schema "audit", Backend.md).

Append-only: the application never UPDATEs or DELETEs rows in this table.
Enforced by convention; only INSERT and SELECT operations are permitted
in this module.
"""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, JSON, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from planner.core.db import Base


def _uuid7() -> uuid.UUID:
    """Generate a UUIDv7 using 48-bit timestamp ms and random bits."""
    unix_ts_ms = int(time.time() * 1000)
    val = (
        (unix_ts_ms << 80)
        | (0x7 << 76)
        | (secrets.randbits(12) << 64)
        | (0x2 << 62)
        | secrets.randbits(62)
    )
    return uuid.UUID(int=val)


class AuditEvent(Base):
    """audit.audit_events table — immutable append-only record of system & user actions."""

    __tablename__ = "audit_events"

    # Backend.md suggests a BRIN index on occurred_at; we use a portable btree
    # index so SQLite and Postgres both work seamlessly in tests and local demo mode.
    __table_args__ = (
        Index("ix_audit_events_occurred_at", "occurred_at"),
        Index("ix_audit_events_event_type", "event_type"),
        Index("ix_audit_events_correlation_id", "correlation_id"),
        {"schema": "audit"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid7)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, default=None)
    user_role: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
