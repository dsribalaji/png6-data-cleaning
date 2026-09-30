"""The ONLY import surface other modules may use (Backend.md).

All external calls into the audit module must pass through this file.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.audit.models import AuditEvent


async def append_audit_event(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    user_role: str | None,
    event_type: str,
    object_type: str,
    object_id: str,
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    """Insert and flush a new audit event row in the caller's transaction.

    NOTE: planner.core.audit.record_audit (owned by W1, currently a stub)
    should delegate to this function — it is the single write path for audit
    events across the system.
    """
    row = AuditEvent(
        user_id=user_id,
        user_role=user_role,
        event_type=event_type,
        object_type=object_type,
        object_id=object_id,
        details=details if details is not None else {},
        correlation_id=correlation_id,
    )
    session.add(row)
    await session.flush()
    return row


__all__ = ["append_audit_event", "AuditEvent"]
