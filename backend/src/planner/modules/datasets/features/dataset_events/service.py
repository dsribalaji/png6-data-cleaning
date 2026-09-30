"""Service for SSE real-time dataset event streaming."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.db import SessionLocal
from planner.core.realtime import get_publisher, sse_event_generator
from planner.modules.datasets.helpers import get_dataset_or_404, replay_job_events


async def dataset_events_service(
    dataset_id: UUID,
    last_event_id: str | None = None,
    session: AsyncSession | None = None,
) -> AsyncGenerator[str, None]:
    """Verify dataset existence and return SSE event stream generator."""
    if session is not None:
        await get_dataset_or_404(session=session, dataset_id=dataset_id)
    else:
        async with SessionLocal() as check_session:
            await get_dataset_or_404(session=check_session, dataset_id=dataset_id)

    publisher = await get_publisher()

    async def _replay(
        d_id: UUID, l_id: str | None
    ) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
        async for item in replay_job_events(d_id, l_id, session_factory=SessionLocal):
            yield item

    return sse_event_generator(
        dataset_id=dataset_id,
        last_event_id=last_event_id,
        replay=_replay,
        publisher=publisher,
    )
