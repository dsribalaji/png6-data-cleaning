"""Router for dataset real-time SSE events."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import get_session
from planner.core.security import RequestPrincipal, get_current_principal
from planner.modules.datasets.features.dataset_events.service import dataset_events_service

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.get("/{id}/events")
async def dataset_events(
    id: UUID,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
    session: AsyncSession = Depends(get_session),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> StreamingResponse:
    """Stream real-time job status updates via Server-Sent Events (SSE)."""
    stream = await dataset_events_service(
        dataset_id=id,
        last_event_id=last_event_id,
        session=session,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
