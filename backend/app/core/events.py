"""Server-Sent Events (SSE) router and event publishing.

Provides real-time event streaming to clients so users do not need to refresh.
"""

import json
from typing import Any, AsyncGenerator
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter(tags=["events"])


def publish_event(topic: str, payload: dict[str, Any]) -> None:
    """Publish an event to subscribers.

    TODO: Back with Redis pub/sub for multi-worker support (PROPOSED: Redis per contract §6, P2).
    Currently an in-memory stub.
    """
    _ = (topic, payload)


async def _event_generator(request: Request) -> AsyncGenerator[dict[str, str], None]:
    """Yield an initial hello event on connection.

    TODO: Connect to Redis pub/sub event bus for live job status updates across Celery workers.
    """
    yield {
        "event": "hello",
        "data": json.dumps({"status": "connected", "message": "PNG6 SSE stream active"}),
    }


@router.get("/stream")
async def event_stream(request: Request) -> EventSourceResponse:
    """Stream Server-Sent Events to the client at /events/stream."""
    return EventSourceResponse(_event_generator(request))
