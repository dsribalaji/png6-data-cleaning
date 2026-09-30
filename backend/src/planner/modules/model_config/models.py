"""SQLAlchemy models for the model_config module (schema "model_config", Backend.md)."""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, Uuid, func, text
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


class ModelConfig(Base):
    """Configuration for LLM inference providers and credentials (schema "model_config")."""

    __tablename__ = "model_configs"
    __table_args__ = (
        Index(
            "uq_model_configs_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active"),
        ),
        {"schema": "model_config"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid7)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    endpoint_url: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    credential_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    credential_last4: Mapped[str | None] = mapped_column(String(4), nullable=True, default=None)
    allow_data_sharing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
