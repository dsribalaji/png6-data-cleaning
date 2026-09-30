"""FastAPI router for the list_audit_events feature slice."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.pagination import Page
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.audit.features.list_audit_events.schemas import (
    AuditEventOut,
    ListAuditEventsInput,
)
from planner.modules.audit.features.list_audit_events.service import list_audit_events

# Auth dependency provided by planner.core.security (owned by W1).
# NOTE: require_roles is wired per spec; currently a foundational dependency.
router = APIRouter(
    prefix="/api/v1/audit-events",
    tags=["audit"],
    dependencies=[Depends(require_roles("auditor", "administrator"))],
)


@router.get("", response_model=Page[AuditEventOut], response_model_by_alias=True)
async def list_audit_events_endpoint(
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    event_type: str | None = Query(default=None, alias="eventType"),
    user_id: UUID | None = Query(default=None, alias="userId"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100, alias="pageSize"),
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(require_roles("auditor", "administrator")),
) -> Page[AuditEventOut]:
    """Retrieve audit events with optional filtering and pagination."""
    input_data = ListAuditEventsInput(
        from_=from_time,
        to=to_time,
        event_type=event_type,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return await list_audit_events(
        session,
        input_data,
        actor_id=principal.user_id,
        actor_role=principal.role,
    )
