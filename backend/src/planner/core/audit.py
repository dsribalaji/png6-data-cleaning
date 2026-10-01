"""Append-only audit log writer, used by every module (Backend.md)."""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


class AuditRecord(BaseModel):
    """Audit log entry payload."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    user_id: UUID | None = None
    user_role: str | None = None
    event_type: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class AuditSink(Protocol):
    """Protocol for recording audit records."""

    async def write(self, record: AuditRecord, session: Any | None = None) -> None:
        """Write an audit record; in ``session``'s transaction when given."""
        ...


_sink: AuditSink | None = None


def bind_audit_sink(sink: AuditSink) -> None:
    """Bind the audit sink implementation (typically provided by modules/audit)."""
    global _sink
    _sink = sink


async def record_audit(
    *args: Any,
    user_id: UUID | None = None,
    user_role: str | None = None,
    event_type: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    details: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    session: Any | None = None,
    **kwargs: Any,
) -> None:
    """Record an audit event, delegating to the bound AuditSink if present."""
    pos = list(args)
    if pos and hasattr(pos[0], "execute"):
        session = session or pos.pop(0)

    fields = {
        "user_id": user_id,
        "user_role": user_role,
        "event_type": event_type,
        "object_type": object_type,
        "object_id": object_id,
        "details": details,
        "correlation_id": correlation_id,
    }
    field_order = [
        "user_id",
        "user_role",
        "event_type",
        "object_type",
        "object_id",
        "details",
        "correlation_id",
    ]
    for key in field_order:
        if fields[key] is None and pos:
            fields[key] = pos.pop(0)

    if _sink is None:
        logger.warning(
            "Audit sink not bound; dropping audit event: %s on %s/%s",
            fields.get("event_type"),
            fields.get("object_type"),
            fields.get("object_id"),
        )
        return

    record = AuditRecord(
        user_id=fields["user_id"],
        user_role=fields["user_role"],
        event_type=str(fields["event_type"] or ""),
        object_type=str(fields["object_type"] or ""),
        object_id=str(fields["object_id"] or ""),
        details=fields["details"] if fields["details"] is not None else {},
        correlation_id=fields["correlation_id"],
    )
    await _sink.write(record, session)
