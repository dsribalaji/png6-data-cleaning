"""Unit tests for the evaluation module (W3)."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import openpyxl
import pytest
from sqlalchemy import ForeignKeyConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from planner.core.db import Base
from planner.core.errors import AppError
from planner.core.events import EventType
from planner.core.outbox import OutboxEvent
from planner.modules.evaluation import adversarial
from planner.modules.evaluation.adversarial import (
    make_injected_instructions_workbook,
    make_malformed_rows_workbook,
    make_sparse_columns_workbook,
    quarantine_check,
    run_adversarial_suite,
)
from planner.modules.evaluation.features.create_evaluation.schemas import CreateEvaluationIn
from planner.modules.evaluation.features.create_evaluation.service import create_evaluation
from planner.modules.evaluation.features.get_evaluation.service import get_evaluation
from planner.modules.evaluation.features.list_evaluations.schemas import ListEvaluationsIn
from planner.modules.evaluation.features.list_evaluations.service import list_evaluations
from planner.modules.evaluation.models import BenchmarkSet, EvaluationRun
from planner.modules.evaluation.public import ensure_default_benchmark_set, get_run
from planner.core.outbox import OutboxEvent
from planner.modules.evaluation.tasks import _run_evaluation_async


@pytest.fixture(scope="session", autouse=True)
def strip_evaluation_schemas() -> None:
    """Per contract §7: strip schemas first before create_all on SQLite."""
    BenchmarkSet.__table__.schema = None
    EvaluationRun.__table__.schema = None
    EvaluationRun.__table__.foreign_keys.clear()
    for col in EvaluationRun.__table__.c:
        col.foreign_keys.clear()
    EvaluationRun.__table__.constraints = {
        c for c in EvaluationRun.__table__.constraints if not isinstance(c, ForeignKeyConstraint)
    }


from sqlalchemy.pool import StaticPool


@pytest.fixture
async def sqlite_engine():
    """Create in-memory SQLite engine with tables initialized."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                BenchmarkSet.__table__,
                EvaluationRun.__table__,
                OutboxEvent.__table__,  # task emits evaluation.completed
            ],
        )
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def session_factory(sqlite_engine):
    """Session factory for the in-memory SQLite test engine."""
    return async_sessionmaker(sqlite_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def session(session_factory):
    """Yield an active AsyncSession connected to SQLite in-memory."""
    async with session_factory() as sess:
        yield sess


# =====================================================================
# Adversarial Fixture Tests
# =====================================================================


def test_adversarial__malformed_rows__quarantined() -> None:
    """Malformed rows workbook must be classified as quarantined."""
    payload = make_malformed_rows_workbook()
    verdict = quarantine_check(payload)
    assert verdict.verdict == "quarantined"
    assert verdict.reason == "malformed rows"


def test_adversarial__injected_instructions__quarantined() -> None:
    """Injected instructions workbook must be classified as quarantined."""
    payload = make_injected_instructions_workbook()
    verdict = quarantine_check(payload)
    assert verdict.verdict == "quarantined"
    assert verdict.reason == "prompt-injection cell"


def test_adversarial__sparse_columns__quarantined() -> None:
    """95%-sparse column workbook must be classified as quarantined."""
    payload = make_sparse_columns_workbook()
    verdict = quarantine_check(payload)
    assert verdict.verdict == "quarantined"
    assert verdict.reason == "sparse column"


def test_adversarial__garbage_bytes__quarantined_without_raising() -> None:
    """Garbage bytes must return quarantined('unparseable workbook') without raising."""
    payload = b"\x00\x01not a workbook"
    verdict = quarantine_check(payload)
    assert verdict.verdict == "quarantined"
    assert verdict.reason == "unparseable workbook"


def test_adversarial__suite_run__all_passed_and_rate_one() -> None:
    """Full adversarial suite must pass with 1.0 quarantine rate."""
    suite = run_adversarial_suite()
    assert suite["passed"] is True
    assert suite["quarantine_rate"] == 1.0
    assert suite["malformed_rows"]["verdict"] == "quarantined"
    assert suite["injected_instructions"]["verdict"] == "quarantined"
    assert suite["sparse_columns"]["verdict"] == "quarantined"


def test_adversarial__runtime_error__returns_crashed_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A task crashing unexpectedly must return verdict='crashed', not raise."""

    def broken_loader(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Synthetic failure in openpyxl loader")

    monkeypatch.setattr(openpyxl, "load_workbook", broken_loader)

    verdict = quarantine_check(b"dummy_payload")
    assert verdict.verdict == "crashed"
    assert "Synthetic failure" in verdict.reason
    assert verdict.detail.get("type") == "RuntimeError"


# =====================================================================
# Service Tests
# =====================================================================


async def test_create_evaluation__default_benchmark__enqueues_and_pending(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Create evaluation without benchmarkSetId creates default set and enqueues task."""
    enqueued_run_id: str | None = None

    def fake_delay(run_id_arg: str) -> MagicMock:
        nonlocal enqueued_run_id
        enqueued_run_id = run_id_arg
        return MagicMock()

    import planner.modules.evaluation.tasks as tasks_module

    monkeypatch.setattr(tasks_module.run_evaluation, "delay", fake_delay)

    out = await create_evaluation(
        session,
        CreateEvaluationIn(),
        actor_id=uuid.uuid4(),
        actor_role="data_engineer",
    )

    assert out.status == "pending"
    assert str(out.id) == enqueued_run_id

    # Verify run row exists in DB with status pending
    run = await get_run(session, out.id)
    assert run.status == "pending"
    assert run.benchmark_set_id is not None

    # Verify default benchmark set was created
    stmt = select(BenchmarkSet).where(BenchmarkSet.name == "adversarial-v1")
    bset = (await session.execute(stmt)).scalar_one_or_none()
    assert bset is not None
    assert bset.id == run.benchmark_set_id


async def test_create_evaluation__custom_benchmark__enqueues_and_pending(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Create evaluation with existing benchmarkSetId references that set."""
    bset = BenchmarkSet(name="custom-set-1", description="custom description", object_keys=[])
    session.add(bset)
    await session.commit()

    monkeypatch.setattr(
        "planner.modules.evaluation.tasks.run_evaluation.delay",
        lambda *args: MagicMock(),
    )

    out = await create_evaluation(
        session,
        CreateEvaluationIn(benchmark_set_id=bset.id),
        actor_id=uuid.uuid4(),
        actor_role="administrator",
    )
    assert out.status == "pending"
    run = await get_run(session, out.id)
    assert run.benchmark_set_id == bset.id


async def test_create_evaluation__missing_benchmark__raises_404(
    session: AsyncSession,
) -> None:
    """Create evaluation with non-existent benchmarkSetId raises 404."""
    with pytest.raises(AppError) as exc_info:
        await create_evaluation(session, CreateEvaluationIn(benchmark_set_id=uuid.uuid4()))
    assert exc_info.value.status == 404
    assert exc_info.value.code == "BENCHMARK_SET_NOT_FOUND"


async def test_get_evaluation__missing_run__raises_404(
    session: AsyncSession,
) -> None:
    """Get evaluation for unknown id raises 404."""
    with pytest.raises(AppError) as exc_info:
        await get_evaluation(session, uuid.uuid4())
    assert exc_info.value.status == 404
    assert exc_info.value.code == "EVALUATION_NOT_FOUND"


async def test_get_evaluation__existing_run__returns_detail(
    session: AsyncSession,
) -> None:
    """Get evaluation returns detail including scores and timestamps."""
    bset = await ensure_default_benchmark_set(session)
    run = EvaluationRun(
        benchmark_set_id=bset.id,
        status="succeeded",
        scores={"passed": True, "quarantine_rate": 1.0},
    )
    session.add(run)
    await session.commit()

    detail = await get_evaluation(session, run.id)
    assert detail.id == run.id
    assert detail.status == "succeeded"
    assert detail.scores == {"passed": True, "quarantine_rate": 1.0}


async def test_list_evaluations__multiple_runs__returns_paginated_page(
    session: AsyncSession,
) -> None:
    """List evaluations returns standard Page envelope ordered by created_at desc."""
    bset = await ensure_default_benchmark_set(session)
    runs = [
        EvaluationRun(benchmark_set_id=bset.id, status="succeeded"),
        EvaluationRun(benchmark_set_id=bset.id, status="pending"),
        EvaluationRun(benchmark_set_id=bset.id, status="failed"),
    ]
    session.add_all(runs)
    await session.commit()

    page = await list_evaluations(session, ListEvaluationsIn(page=1, page_size=2))
    assert page.page == 1
    assert page.page_size == 2
    assert page.total >= 3
    assert len(page.items) == 2


async def test_public_api__ensure_default_benchmark_set__idempotent(
    session: AsyncSession,
) -> None:
    """ensure_default_benchmark_set creates once and reuses on subsequent calls."""
    b1 = await ensure_default_benchmark_set(session)
    b2 = await ensure_default_benchmark_set(session)
    assert b1.id == b2.id
    assert b1.name == "adversarial-v1"


# =====================================================================
# Celery Task Execution & Idempotency Tests
# =====================================================================


async def test_tasks__run_evaluation__transitions_to_succeeded_and_emits_event(
    session: AsyncSession, session_factory: Any
) -> None:
    """_run_evaluation_async marks run running, succeeded, and emits outbox event."""
    bset = await ensure_default_benchmark_set(session)
    run = EvaluationRun(benchmark_set_id=bset.id, status="pending")
    session.add(run)
    await session.commit()
    run_id_str = str(run.id)

    scores = await _run_evaluation_async(run_id_str, session_factory=session_factory)
    assert scores["passed"] is True

    # Verify run and outbox in DB using fresh session
    async with session_factory() as verify_session:
        refreshed_run = await get_run(verify_session, run.id)
        assert refreshed_run.status == "succeeded"
        assert refreshed_run.scores is not None
        assert refreshed_run.scores["passed"] is True
        assert refreshed_run.started_at is not None
        assert refreshed_run.finished_at is not None

        # Verify outbox event was recorded
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.event_type == EventType.EVALUATION_COMPLETED.value)
            .order_by(OutboxEvent.created_at.desc())
        )
        result = await verify_session.execute(stmt)
        outbox_event = result.scalars().first()
        assert outbox_event is not None
        assert outbox_event.payload.get("evaluationId") == run_id_str
        assert outbox_event.payload.get("passed") is True

    # Idempotency: re-running against already succeeded run should exit early
    second_run = await _run_evaluation_async(run_id_str, session_factory=session_factory)
    assert second_run.get("early_exit") is True
    assert second_run.get("status") == "succeeded"


async def test_tasks__run_evaluation__failed_run__records_failure_and_reraises(
    session: AsyncSession, session_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On execution error, _run_evaluation_async marks failed, records error, and re-raises."""
    bset = await ensure_default_benchmark_set(session)
    run = EvaluationRun(benchmark_set_id=bset.id, status="pending")
    session.add(run)
    await session.commit()
    run_id_str = str(run.id)

    def crashing_suite() -> dict[str, Any]:
        raise ValueError("Simulated task error during suite execution")

    monkeypatch.setattr(adversarial, "run_adversarial_suite", crashing_suite)

    with pytest.raises(ValueError, match="Simulated task error"):
        await _run_evaluation_async(run_id_str, session_factory=session_factory)

    async with session_factory() as verify_session:
        refreshed_run = await get_run(verify_session, run.id)
        assert refreshed_run.status == "failed"
        assert "Simulated task error" in str(refreshed_run.error_message)
        assert refreshed_run.finished_at is not None
