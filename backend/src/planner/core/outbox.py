"""Transactional outbox (Backend.md).

A state change writes a row plus an outbox event in ONE database transaction.
The relay (beat task) publishes unpublished rows to the message broker.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery import shared_task
from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Index, Text, Uuid, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from planner.core.db import Base, uuid7
from planner.core.events import EventPayload, EventType


class OutboxEvent(Base):
    """public.outbox - rows with published_at IS NULL are picked up by the relay."""

    __tablename__ = "outbox"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    event_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    __table_args__ = (
        Index(
            "ix_outbox_published_at_null",
            "published_at",
            sqlite_where=text("published_at IS NULL"),
            postgresql_where=text("published_at IS NULL"),
        ),
    )


# Backwards compatibility alias
Outbox = OutboxEvent

_HANDLERS: dict[str, str] = {}


def register_outbox_handler(event_type: str, task_name: str) -> None:
    """Register a Celery task name to handle a given outbox event type."""
    _HANDLERS[event_type] = task_name


def get_outbox_handler(event_type: str) -> str | None:
    """Retrieve the registered task name for an outbox event type."""
    return _HANDLERS.get(event_type)


async def add_event(
    session: AsyncSession, event_type: str, payload: BaseModel | dict[str, Any]
) -> OutboxEvent:
    """Append an outbox row in the caller's transaction (Backend.md)."""
    if isinstance(payload, BaseModel):
        payload_data = payload.model_dump(by_alias=True, mode="json")
    else:
        payload_data = payload

    row = OutboxEvent(event_type=event_type, payload=payload_data)
    session.add(row)
    await session.flush()
    return row


async def emit(
    session: AsyncSession, event: EventType, payload: EventPayload
) -> OutboxEvent:
    """Type-safe outbox emission using EventType and EventPayload."""
    event_str = event.value if isinstance(event, EventType) else str(event)
    return await add_event(session, event_str, payload)


async def _async_relay(limit: int = 100, task_instance: Any = None) -> int:
    from planner.core.config import settings
    from planner.core.db import SessionLocal

    celery = getattr(task_instance, "app", None)
    if celery is None:
        try:
            from planner.worker import celery_app as celery
        except ImportError:
            celery = None

    published_count = 0
    async with SessionLocal() as session:
        try:
            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at.asc())
                .limit(limit)
            )
            if settings.database_url.startswith("postgresql"):
                stmt = stmt.with_for_update(skip_locked=True)

            result = await session.execute(stmt)
            rows = result.scalars().all()

            now = datetime.now(UTC)
            for row in rows:
                task_name = get_outbox_handler(row.event_type)
                if task_name and celery is not None:
                    payload_kwargs = (
                        dict(row.payload)
                        if isinstance(row.payload, dict)
                        else {"payload": row.payload}
                    )
                    celery.send_task(task_name, kwargs=payload_kwargs)
                row.published_at = now
                published_count += 1

            await session.commit()
            return published_count
        except Exception:
            await session.rollback()
            raise


@shared_task(bind=True, name="planner.core.outbox.relay_outbox", max_retries=3)
def relay_outbox(self: Any = None, limit: int = 100) -> int:
    """Publish unpublished outbox rows to the Celery broker."""
    actual_self = self
    actual_limit = limit
    if isinstance(self, int):
        actual_self = None
        actual_limit = self

    try:
        return asyncio.run(_async_relay(limit=actual_limit, task_instance=actual_self))
    except Exception as exc:
        if actual_self is not None and hasattr(actual_self, "retry"):
            retries = getattr(actual_self.request, "retries", 0)
            countdown = (2**retries) * 5
            raise actual_self.retry(exc=exc, countdown=countdown)
        raise


RELAY_OUTBOX_TASK_NAME = "planner.core.outbox.relay_outbox"
RELAY_OUTBOX_ALIAS = "planner.relay_outbox"


def register_tasks(celery_app: Any) -> None:
    """Ensure relay_outbox is registered on the provided Celery app instance.

    ``shared_task`` registers the task on every finalized Celery app, so this
    finalizes the app and adds the legacy ``planner.relay_outbox`` alias. The
    task object must NOT be passed to ``registry.register``: it is a lazy
    Proxy, and storing the Proxy in the registry makes every later attribute
    access on the task recurse infinitely.
    """
    celery_app.tasks  # noqa: B018 - accessing the registry finalizes the app
    if RELAY_OUTBOX_ALIAS not in celery_app.tasks:
        celery_app.tasks[RELAY_OUTBOX_ALIAS] = celery_app.tasks[RELAY_OUTBOX_TASK_NAME]
