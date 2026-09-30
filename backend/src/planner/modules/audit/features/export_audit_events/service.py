"""Service layer for the export_audit_events feature slice."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.modules.audit.features.export_audit_events.schemas import (
    ExportAuditEventsInput,
    ExportAuditEventsOut,
)
from planner.modules.audit.models import AuditEvent

# Cap export to 100,000 rows to prevent unbounded memory usage (spec requirement).
MAX_EXPORT_ROWS = 100_000


async def export_audit_events(
    session: AsyncSession,
    input: ExportAuditEventsInput,
    *,
    actor_id: UUID | None = None,
    actor_role: str = "system",
) -> ExportAuditEventsOut:
    """Export filtered audit events to CSV format.

    Builds CSV into io.StringIO with standard audit columns and serialized details.
    Restricted to at most 100,000 rows as per system guardrails.
    """
    filters = []
    if input.from_ is not None:
        filters.append(AuditEvent.occurred_at >= input.from_)
    if input.to is not None:
        filters.append(AuditEvent.occurred_at <= input.to)
    if input.event_type is not None:
        filters.append(AuditEvent.event_type == input.event_type)
    if input.user_id is not None:
        filters.append(AuditEvent.user_id == input.user_id)

    query_stmt = select(AuditEvent)
    if filters:
        query_stmt = query_stmt.where(and_(*filters))
    query_stmt = (
        query_stmt.order_by(AuditEvent.occurred_at.desc())
        .limit(MAX_EXPORT_ROWS)
    )

    result = await session.execute(query_stmt)
    rows = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "occurred_at",
        "user_id",
        "user_role",
        "event_type",
        "object_type",
        "object_id",
        "correlation_id",
        "details_json",
    ])

    for row in rows:
        writer.writerow([
            str(row.id),
            (
                row.occurred_at.isoformat()
                if hasattr(row.occurred_at, "isoformat")
                else str(row.occurred_at)
            ),
            str(row.user_id) if row.user_id is not None else "",
            row.user_role or "",
            row.event_type,
            row.object_type,
            row.object_id,
            row.correlation_id or "",
            json.dumps(row.details if row.details is not None else {}),
        ])

    csv_content = output.getvalue()
    now = datetime.now(timezone.utc)
    filename = f"audit-events-{now.strftime('%Y%m%d-%H%M%S')}.csv"

    return ExportAuditEventsOut(
        csv_content=csv_content,
        filename=filename,
        row_count=len(rows),
    )
