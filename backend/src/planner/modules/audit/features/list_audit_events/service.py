"""Service layer for the list_audit_events feature slice."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.pagination import Page, build_page
from planner.modules.audit.features.list_audit_events.schemas import (
    AuditEventOut,
    ListAuditEventsInput,
)
from planner.modules.audit.models import AuditEvent


async def list_audit_events(
    session: AsyncSession,
    input: ListAuditEventsInput,
    *,
    actor_id: UUID | None = None,
    actor_role: str = "system",
) -> Page[AuditEventOut]:
    """Retrieve a paginated list of audit events matching filter criteria.

    Orders results by occurred_at descending.
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

    count_stmt = select(func.count()).select_from(AuditEvent)
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()

    offset = (input.page - 1) * input.page_size
    query_stmt = select(AuditEvent)
    if filters:
        query_stmt = query_stmt.where(and_(*filters))
    query_stmt = (
        query_stmt.order_by(AuditEvent.occurred_at.desc())
        .offset(offset)
        .limit(input.page_size)
    )

    result = await session.execute(query_stmt)
    rows = result.scalars().all()

    items = [AuditEventOut.model_validate(row) for row in rows]
    return build_page(
        items=items,
        total=total,
        page=input.page,
        page_size=input.page_size,
    )
