"""Service-level unit tests for dataset_events feature (replay + SSE formatting)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base, uuid7
from planner.core.realtime import format_sse, sse_event_generator
from planner.modules.datasets.helpers import create_job, replay_job_events
from planner.modules.datasets.models import Dataset


@pytest.fixture
async def session_factory() -> async_sessionmaker[AsyncSession]:
    """Provide an in-memory SQLite session factory with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory

    await engine.dispose()


@pytest.fixture
async def dataset(session_factory: async_sessionmaker[AsyncSession]) -> Dataset:
    """Seed one dataset and return it."""
    async with session_factory() as session:
        row = Dataset(
            id=uuid7(),
            name="invoices.csv",
            source="upload",
            file_name="invoices.csv",
            status="profiling",
            row_count=3,
            column_count=2,
            version=1,
        )
        session.add(row)
        await session.commit()
        return row


@pytest.mark.asyncio
async def test_dataset_events__two_jobs__replays_in_order_with_correct_fields(
    session_factory: async_sessionmaker[AsyncSession],
    dataset: Dataset,
) -> None:
    """Replay yields both jobs oldest-first with camelCase fields and the SSE id."""
    plan_id = uuid7()
    base = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)

    async with session_factory() as session:
        first = await create_job(session=session, dataset_id=dataset.id, type="ingest")
        second = await create_job(
            session=session,
            dataset_id=dataset.id,
            type="profile",
            plan_id=plan_id,
        )
        first_id, second_id = first.id, second.id

        # created_at is server_default; pin distinct values so ordering and the
        # Last-Event-ID cutoff are deterministic.
        first.created_at = base
        second.created_at = base + timedelta(seconds=1)
        second.status = "succeeded"
        second.progress_pct = 100.0
        await session.commit()

    events: list[tuple[str, dict[str, object]]] = []
    async for event_id, data in replay_job_events(
        dataset.id, None, session_factory=session_factory
    ):
        events.append((event_id, data))

    assert len(events) == 2
    assert [e[0] for e in events] == [str(first_id), str(second_id)]

    first_event, first_data = events[0]
    assert first_event == str(first_id)
    assert first_data["jobId"] == str(first_id)
    assert first_data["type"] == "ingest"
    assert first_data["status"] == "queued"
    assert first_data["progressPct"] == 0.0
    assert first_data["message"] == "Job ingest queued"
    assert "planId" not in first_data

    _, second_data = events[1]
    assert second_data["jobId"] == str(second_id)
    assert second_data["type"] == "profile"
    assert second_data["status"] == "succeeded"
    assert second_data["progressPct"] == 100.0
    assert second_data["planId"] == str(plan_id)


@pytest.mark.asyncio
async def test_dataset_events__last_event_id__skips_older_events(
    session_factory: async_sessionmaker[AsyncSession],
    dataset: Dataset,
) -> None:
    """A Last-Event-ID equal to the first job replays only the later job."""
    base = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)

    async with session_factory() as session:
        first = await create_job(session=session, dataset_id=dataset.id, type="ingest")
        second = await create_job(session=session, dataset_id=dataset.id, type="profile")
        first_id, second_id = first.id, second.id
        first.created_at = base
        second.created_at = base + timedelta(seconds=1)
        await session.commit()

    events = [
        (event_id, data)
        async for event_id, data in replay_job_events(
            dataset.id, str(first_id), session_factory=session_factory
        )
    ]

    assert len(events) == 1
    assert events[0][0] == str(second_id)
    assert events[0][1]["jobId"] == str(second_id)


@pytest.mark.asyncio
async def test_dataset_events__no_jobs__replays_nothing(
    session_factory: async_sessionmaker[AsyncSession],
    dataset: Dataset,
) -> None:
    """A dataset with no job rows produces an empty replay."""
    events = [
        item
        async for item in replay_job_events(
            dataset.id, None, session_factory=session_factory
        )
    ]

    assert events == []


@pytest.mark.asyncio
async def test_dataset_events__format_sse__emits_id_and_json_data_line() -> None:
    """format_sse produces an `id:` line and a compact `data:` line."""
    chunk = format_sse("job-1", {"jobId": "job-1", "progressPct": 12.5})

    assert chunk == (
        'id: job-1\ndata: {"jobId":"job-1","progressPct":12.5}\n\n'
    )
    header, data_line, *rest = chunk.split("\n")
    assert header == "id: job-1"
    assert rest == ["", ""]
    assert json.loads(data_line.removeprefix("data: ")) == {
        "jobId": "job-1",
        "progressPct": 12.5,
    }


class StubPublisher:
    """Publisher stub yielding one live message then ending the subscription."""

    def __init__(self, message: dict[str, object]) -> None:
        self.message = message
        self.published_channels: list[str] = []

    async def publish(self, channel: str, message: dict[str, object]) -> None:
        self.published_channels.append(channel)
        await asyncio.sleep(0)

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, object]]:
        assert channel.startswith("jobs:")
        yield self.message


@pytest.mark.asyncio
async def test_dataset_events__sse_generator__streams_replay_then_live_events() -> None:
    """The generator emits replayed chunks first, then live pub/sub messages."""
    dataset_id = uuid7()
    publisher = StubPublisher(
        {"jobId": "live-1", "type": "ingest", "status": "running", "progressPct": 10.0}
    )

    async def _replay(
        _dataset_id: UUID, _last_event_id: str | None
    ) -> AsyncIterator[tuple[str, dict[str, object]]]:
        yield "replay-1", {"jobId": "replay-1", "type": "ingest", "status": "queued"}

    generator = sse_event_generator(
        dataset_id=dataset_id,
        last_event_id=None,
        replay=_replay,
        publisher=publisher,
    )

    first = await anext(generator)
    second = await anext(generator)
    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    assert first.startswith("id: replay-1\ndata: ")
    assert json.loads(first.split("data: ", 1)[1])["status"] == "queued"
    assert second.startswith("id: live-1\ndata: ")
    assert json.loads(second.split("data: ", 1)[1])["status"] == "running"