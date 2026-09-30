"""Async database engine, session factory, and declarative base (Backend.md)."""

from __future__ import annotations

import os
import time
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from planner.core.config import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base with constraint naming conventions (Backend.md)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _create_engine() -> AsyncEngine:
    if settings.database_url.startswith("sqlite"):
        return create_async_engine(
            settings.database_url,
            echo=False,
            poolclass=NullPool,
            execution_options={
                "schema_translate_map": {
                    "profiling": None,
                    "planning": None,
                    "datasets": None,
                    "users": None,
                    "execution": None,
                    "validation": None,
                    "model_config": None,
                    "audit": None,
                    "evaluation": None,
                }
            },
        )
    return create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)


engine: AsyncEngine = _create_engine()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an AsyncSession, rolling back on error."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def schema_for(module: str) -> str | None:
    """Return the schema name for postgresql, or None for sqlite."""
    if settings.database_url.startswith("postgresql"):
        return module
    return None


def uuid7() -> UUID:
    """Generate an RFC 9562 UUIDv7 (48-bit unix-ms timestamp, ver 0111, variant 10)."""
    ms = int(time.time() * 1000)
    time_bytes = ms.to_bytes(6, byteorder="big")
    rand = os.urandom(10)
    b6 = (0x70 | (rand[0] & 0x0F)).to_bytes(1, "big")
    b7 = rand[1:2]
    b8 = (0x80 | (rand[2] & 0x3F)).to_bytes(1, "big")
    rest = rand[3:]
    return UUID(bytes=time_bytes + b6 + b7 + b8 + rest)


new_id = uuid7


async def init_db() -> None:
    """Create all tables (local demo convenience)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
