"""SQLAlchemy models for the users module (schema "users", Backend.md).

Portable across PostgreSQL and SQLite per contract 10.3/10.7.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from planner.core.db import Base, schema_for, uuid7

SCHEMA = schema_for("users")
USERS_TABLE_REF = f"{SCHEMA}.users.id" if SCHEMA else "users.id"

VALID_ROLES: set[str] = {"data_engineer", "administrator", "auditor", "viewer"}
VALID_STATUSES: set[str] = {"invited", "active", "deactivated"}


class User(Base):
    """User account entity."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('invited', 'active', 'deactivated')",
            name="ck_users_status",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="invited")
    failed_logins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    role_rel: Mapped[UserRole | None] = relationship(
        "UserRole",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class UserRole(Base):
    """User role mapping: exactly one role per user (OQ-21)."""

    __tablename__ = "user_roles"
    __table_args__ = (
        CheckConstraint(
            "role IN ('data_engineer', 'administrator', 'auditor', 'viewer')",
            name="ck_user_roles_role",
        ),
        {"schema": SCHEMA},
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(USERS_TABLE_REF, ondelete="CASCADE"),
        primary_key=True,
        unique=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="role_rel")


class RefreshToken(Base):
    """Rotating refresh token with family tracking for reuse detection."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_family_id", "family_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(USERS_TABLE_REF, ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    family_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")


class Invite(Base):
    """User invite token record."""

    __tablename__ = "invites"
    __table_args__ = (
        CheckConstraint(
            "role IN ('data_engineer', 'administrator', 'auditor', 'viewer')",
            name="ck_invites_role",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
