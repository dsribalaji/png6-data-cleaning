"""FastAPI router for the export_audit_events feature slice."""

from __future__ import annotations

import io
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, require_roles
from planner.modules.audit.features.export_audit_events.schemas import ExportAuditEventsInput
from planner.modules.audit.features.export_audit_events.service import export_audit_events

# Auth dependency provided by planner.core.security (owned by W1).
# NOTE: require_roles is wired per spec; export is strictly restricted to auditor role only
# (Backend.md: administrator gets GET-only on audit; export is auditor-only).
router = APIRouter(
    prefix="/api/v1/audit-events",
    tags=["audit"],
    dependencies=[Depends(require_roles("auditor"))],
)


@router.get("/export")
async def export_audit_events_endpoint(
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    event_type: str | None = Query(default=None, alias="eventType"),
    user_id: UUID | None = Query(default=None, alias="userId"),
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(require_roles("auditor")),
) -> StreamingResponse:
    """Export audit events as a downloadable CSV file (auditor role only)."""
    input_data = ExportAuditEventsInput(
        from_=from_time,
        to=to_time,
        event_type=event_type,
        user_id=user_id,
    )
    result = await export_audit_events(
        session,
        input_data,
        actor_id=principal.user_id,
        actor_role=principal.role,
    )
    return StreamingResponse(
        io.StringIO(result.csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )
