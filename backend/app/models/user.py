"""User database model."""

from datetime import datetime, timezone
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk


class User(Base, UUIDPk):
    """User account entity.

    PROPOSED (contract §6, P3): One role per user.
    Standard roles: data_engineer, administrator, auditor.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # PROPOSED: one role per user (contract §6, P3)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="data_engineer")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
