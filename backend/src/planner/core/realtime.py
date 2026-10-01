"""Redis pub/sub publisher + SSE endpoint helper (Backend.md).

The relay/workers publish job.status on Redis channel jobs:{datasetId};
GET /api/v1/datasets/{id}/events streams them to the browser with a
15 s heartbeat and Last-Event-ID replay from the jobs table.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any, Protocol
from uuid import UUID

from planner.core.config import settings
from planner.core.events import JobStatusPayload

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    """Protocol for pub/sub message dissemination."""

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Publish a dictionary message to the specified channel."""
        ...

    async def subscribe(self, channel: str) -> AsyncGenerator[dict[str, Any], None]:
        """Subscribe to a channel and yield received dictionary messages."""
        ...


class RedisEventPublisher:
    """Redis-backed pub/sub event publisher."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._redis: Any = None

    async def _get_client(self) -> Any:
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self.url, decode_responses=True)
        return self._redis

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        client = await self._get_client()
        payload_str = json.dumps(message, separators=(",", ":"))
        await client.publish(channel, payload_str)

    async def subscribe(self, channel: str) -> AsyncGenerator[dict[str, Any], None]:
        client = await self._get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for raw in pubsub.listen():
                if raw and raw.get("type") == "message":
                    data = raw.get("data")
                    if isinstance(data, (str, bytes)):
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError as exc:
                            logger.warning(
                                "Dropping malformed JSON payload on channel %s: %s",
                                channel,
                                exc,
                            )
                    elif isinstance(data, dict):
                        yield data
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception as exc:  # noqa: BLE001 -- pubsub teardown must never raise
                logger.warning("Failed to clean up redis pubsub subscription: %s", exc)


class InMemoryEventPublisher:
    """In-memory pub/sub fallback for local demo and offline development."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(channel, []))
        for q in queues:
            await q.put(message)

    async def subscribe(self, channel: str) -> AsyncGenerator[dict[str, Any], None]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            if channel not in self._subscribers:
                self._subscribers[channel] = []
            self._subscribers[channel].append(q)
        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            async with self._lock:
                if channel in self._subscribers and q in self._subscribers[channel]:
                    self._subscribers[channel].remove(q)
                    if not self._subscribers[channel]:
                        del self._subscribers[channel]


_publisher: EventPublisher | None = None


async def get_publisher() -> EventPublisher:
    """Return a singleton EventPublisher, falling back to InMemory if Redis fails."""
    global _publisher
    if _publisher is not None:
        return _publisher

    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url)
        await asyncio.wait_for(client.ping(), timeout=1.0)
        await client.aclose()
        _publisher = RedisEventPublisher(settings.redis_url)
        return _publisher
    except Exception as exc:  # noqa: BLE001 -- any redis failure falls back to in-memory
        logger.warning(
            "Redis connection failed (%s); falling back to InMemoryEventPublisher",
            exc,
        )
        _publisher = InMemoryEventPublisher()
        return _publisher


async def publish_job_status(dataset_id: UUID, payload: JobStatusPayload) -> None:
    """Publish a JobStatusPayload message to the channel jobs:{dataset_id}."""
    pub = await get_publisher()
    channel = f"jobs:{dataset_id}"
    await pub.publish(channel, payload.model_dump(by_alias=True, mode="json"))


def format_sse(event_id: str, data: dict[str, Any]) -> str:
    """Format an SSE message chunk with ID and JSON payload."""
    serialized = json.dumps(data, separators=(",", ":"))
    return f"id: {event_id}\ndata: {serialized}\n\n"


async def sse_event_generator(
    dataset_id: UUID,
    last_event_id: str | None = None,
    replay: (
        Callable[[UUID, str | None], AsyncGenerator[tuple[str, dict[str, Any]], None]]
        | None
    ) = None,
    publisher: EventPublisher | None = None,
) -> AsyncGenerator[str, None]:
    """SSE generator streaming replayed events followed by live pub/sub events with heartbeats."""
    if replay is not None:
        async for event_id, data in replay(dataset_id, last_event_id):
            yield format_sse(str(event_id), data)

    pub = publisher if publisher is not None else await get_publisher()
    channel = f"jobs:{dataset_id}"
    subscription = pub.subscribe(channel)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(anext(subscription), timeout=15.0)
                event_id = str(msg.get("job_id", msg.get("jobId", "")))
                yield format_sse(event_id, msg)
            except TimeoutError:
                yield ": heartbeat\n\n"
            except StopAsyncIteration:
                break
    finally:
        if hasattr(subscription, "aclose"):
            await subscription.aclose()


# Backwards compatibility alias
sse_event_stream = sse_event_generator
