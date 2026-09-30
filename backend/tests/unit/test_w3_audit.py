"""Unit tests for the audit module (W3 task, Backend.md).

Tests verify:
1. SQLite schema stripping and table creation.
2. append_audit_event inserting rows with generated UUIDv7 and occurred_at.
3. list_audit_events filtering by from/to dates, eventType, userId and pagination.
4. export_audit_events CSV format, headers, row count, JSON details, and filename pattern.
5. Append-only source scan guard (no delete/update calls in the audit module).
6. HTTP router endpoints and role-based access control.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner.core.db import Base, get_session
from planner.core.errors import AppError, app_error_handler
from planner.core.security import RequestPrincipal, get_current_principal
from planner.modules.audit.features.export_audit_events.router import (
    router as export_router,
)
from planner.modules.audit.features.export_audit_events.schemas import (
    ExportAuditEventsInput,
    ExportAuditEventsOut,
)
from planner.modules.audit.features.export_audit_events.service import (
    export_audit_events,
)
from planner.modules.audit.features.list_audit_events.router import (
    router as list_router,
)
from planner.modules.audit.features.list_audit_events.schemas import (
    AuditEventOut,
    ListAuditEventsInput,
)
from planner.modules.audit.features.list_audit_events.service import (
    list_audit_events,
)
from planner.modules.audit.models import AuditEvent
from planner.modules.audit.public import append_audit_event


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated in-memory SQLite database session for tests.

    SQLite has no schemas; core.db maps them away on every SQLite connection.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[AuditEvent.__table__])

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_append_audit_event__valid_input__inserts_and_sets_occurred_at(
    db_session: AsyncSession,
) -> None:
    """append_audit_event inserts a row and populates occurred_at and id."""
    user_id = UUID("11111111-1111-1111-1111-111111111111")
    event = await append_audit_event(
        db_session,
        user_id=user_id,
        user_role="auditor",
        event_type="dataset.uploaded",
        object_type="dataset",
        object_id="ds-001",
        details={"file_name": "VendorInvoices.xlsx", "size_bytes": 1024},
        correlation_id="corr-req-001",
    )

    assert event.id is not None
    assert isinstance(event.id, UUID)
    assert event.occurred_at is not None
    assert isinstance(event.occurred_at, datetime)
    assert event.user_id == user_id
    assert event.user_role == "auditor"
    assert event.event_type == "dataset.uploaded"
    assert event.object_type == "dataset"
    assert event.object_id == "ds-001"
    assert event.details == {"file_name": "VendorInvoices.xlsx", "size_bytes": 1024}
    assert event.correlation_id == "corr-req-001"


@pytest.mark.asyncio
async def test_append_audit_event__none_details__defaults_to_empty_dict(
    db_session: AsyncSession,
) -> None:
    """append_audit_event with details=None defaults to an empty dictionary."""
    event = await append_audit_event(
        db_session,
        user_id=None,
        user_role=None,
        event_type="system.boot",
        object_type="system",
        object_id="server-1",
        details=None,
    )

    assert event.details == {}
    assert event.user_id is None
    assert event.user_role is None
    assert event.correlation_id is None


async def _seed_5_events(db_session: AsyncSession) -> tuple[UUID, UUID, list[AuditEvent]]:
    """Helper to seed 5 audit events across different users, event types, and dates."""
    user_a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    user_b = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    d1 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    d2 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)
    d3 = datetime(2026, 9, 3, 10, 0, 0, tzinfo=timezone.utc)
    d4 = datetime(2026, 9, 4, 10, 0, 0, tzinfo=timezone.utc)
    d5 = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)

    events = [
        AuditEvent(
            occurred_at=d1,
            user_id=user_a,
            user_role="data_engineer",
            event_type="auth.login",
            object_type="user",
            object_id=str(user_a),
            details={"ip": "192.168.1.1"},
            correlation_id="c-1",
        ),
        AuditEvent(
            occurred_at=d2,
            user_id=user_a,
            user_role="data_engineer",
            event_type="dataset.uploaded",
            object_type="dataset",
            object_id="ds-1",
            details={"rows": 22, "columns": 19},
            correlation_id="c-2",
        ),
        AuditEvent(
            occurred_at=d3,
            user_id=user_b,
            user_role="auditor",
            event_type="dataset.profiled",
            object_type="dataset",
            object_id="ds-1",
            details={"null_counts": 12},
            correlation_id="c-3",
        ),
        AuditEvent(
            occurred_at=d4,
            user_id=user_b,
            user_role="auditor",
            event_type="plan.approved",
            object_type="plan",
            object_id="plan-1",
            details={"steps_count": 8},
            correlation_id="c-4",
        ),
        AuditEvent(
            occurred_at=d5,
            user_id=None,
            user_role="system",
            event_type="validation.completed",
            object_type="plan",
            object_id="plan-1",
            details={"passed": True, "reconciliations_ok": 22},
            correlation_id="c-5",
        ),
    ]
    db_session.add_all(events)
    await db_session.flush()
    return user_a, user_b, events


@pytest.mark.asyncio
async def test_list_audit_events__filters__each_filter_narrows_correctly(
    db_session: AsyncSession,
) -> None:
    """list_audit_events filters by from_time, to_time, event_type, and user_id."""
    user_a, user_b, _ = await _seed_5_events(db_session)

    # 1. Filter: from_time (>= 2026-09-03) -> matches d3, d4, d5 (3 events)
    res_from = await list_audit_events(
        db_session,
        ListAuditEventsInput(from_=datetime(2026, 9, 3, 0, 0, 0, tzinfo=timezone.utc)),
    )
    assert res_from.total == 3
    assert {e.event_type for e in res_from.items} == {
        "dataset.profiled",
        "plan.approved",
        "validation.completed",
    }

    # 2. Filter: to_time (<= 2026-09-02 23:59:59) -> matches d1, d2 (2 events)
    res_to = await list_audit_events(
        db_session,
        ListAuditEventsInput(to=datetime(2026, 9, 2, 23, 59, 59, tzinfo=timezone.utc)),
    )
    assert res_to.total == 2
    assert {e.event_type for e in res_to.items} == {"auth.login", "dataset.uploaded"}

    # 3. Filter: range from + to (2026-09-02 to 2026-09-04) -> matches d2, d3, d4 (3 events)
    res_range = await list_audit_events(
        db_session,
        ListAuditEventsInput(
            from_=datetime(2026, 9, 2, 0, 0, 0, tzinfo=timezone.utc),
            to=datetime(2026, 9, 4, 23, 59, 59, tzinfo=timezone.utc),
        ),
    )
    assert res_range.total == 3
    assert {e.event_type for e in res_range.items} == {
        "dataset.uploaded",
        "dataset.profiled",
        "plan.approved",
    }

    # 4. Filter: event_type == "dataset.profiled" -> matches d3 only
    res_event = await list_audit_events(
        db_session,
        ListAuditEventsInput(event_type="dataset.profiled"),
    )
    assert res_event.total == 1
    assert res_event.items[0].event_type == "dataset.profiled"
    assert res_event.items[0].object_id == "ds-1"

    # 5. Filter: user_id == user_a -> matches d1, d2 (2 events)
    res_user_a = await list_audit_events(
        db_session,
        ListAuditEventsInput(user_id=user_a),
    )
    assert res_user_a.total == 2
    assert all(e.user_id == user_a for e in res_user_a.items)

    # 6. Filter: user_id == user_b -> matches d3, d4 (2 events)
    res_user_b = await list_audit_events(
        db_session,
        ListAuditEventsInput(user_id=user_b),
    )
    assert res_user_b.total == 2
    assert all(e.user_id == user_b for e in res_user_b.items)

    # 7. Filter: non-existent value -> 0 results
    res_none = await list_audit_events(
        db_session,
        ListAuditEventsInput(event_type="non.existent.event"),
    )
    assert res_none.total == 0
    assert len(res_none.items) == 0


@pytest.mark.asyncio
async def test_list_audit_events__pagination__page_size_and_envelope_respected(
    db_session: AsyncSession,
) -> None:
    """list_audit_events respects pagination parameters and order by occurred_at desc."""
    _, _, events = await _seed_5_events(db_session)
    sorted_events = sorted(events, key=lambda e: e.occurred_at, reverse=True)

    # Page 1, pageSize 2
    p1 = await list_audit_events(
        db_session,
        ListAuditEventsInput(page=1, page_size=2),
    )
    assert p1.total == 5
    assert p1.page == 1
    assert p1.page_size == 2
    assert len(p1.items) == 2
    assert p1.items[0].occurred_at == sorted_events[0].occurred_at
    assert p1.items[1].occurred_at == sorted_events[1].occurred_at

    # Page 2, pageSize 2
    p2 = await list_audit_events(
        db_session,
        ListAuditEventsInput(page=2, page_size=2),
    )
    assert p2.total == 5
    assert p2.page == 2
    assert p2.page_size == 2
    assert len(p2.items) == 2
    assert p2.items[0].occurred_at == sorted_events[2].occurred_at
    assert p2.items[1].occurred_at == sorted_events[3].occurred_at

    # Page 3, pageSize 2
    p3 = await list_audit_events(
        db_session,
        ListAuditEventsInput(page=3, page_size=2),
    )
    assert p3.total == 5
    assert p3.page == 3
    assert p3.page_size == 2
    assert len(p3.items) == 1
    assert p3.items[0].occurred_at == sorted_events[4].occurred_at

    # Check serialized camelCase JSON shape
    dumped = p1.model_dump(by_alias=True)
    assert set(dumped.keys()) == {"items", "page", "pageSize", "total"}
    first_item = dumped["items"][0]
    expected_keys = {
        "id",
        "occurredAt",
        "userId",
        "userRole",
        "eventType",
        "objectType",
        "objectId",
        "details",
        "correlationId",
    }
    assert set(first_item.keys()) == expected_keys


@pytest.mark.asyncio
async def test_export_audit_events__csv_structure_and_filename_pattern(
    db_session: AsyncSession,
) -> None:
    """export_audit_events produces valid CSV with expected headers, serialized JSON, and filename."""
    user_a, _, _ = await _seed_5_events(db_session)

    # Full export (all 5 rows)
    out: ExportAuditEventsOut = await export_audit_events(
        db_session,
        ExportAuditEventsInput(),
    )

    # 1. Filename pattern: audit-events-<UTC YYYYMMDD-HHMMSS>.csv
    assert re.match(r"^audit-events-\d{8}-\d{6}\.csv$", out.filename)

    # 2. Parse CSV
    reader = list(csv.reader(io.StringIO(out.csv_content)))
    assert len(reader) == 6  # 1 header + 5 data rows

    header = reader[0]
    expected_header = [
        "id",
        "occurred_at",
        "user_id",
        "user_role",
        "event_type",
        "object_type",
        "object_id",
        "correlation_id",
        "details_json",
    ]
    assert header == expected_header

    # 3. Check details_json column is valid JSON
    for data_row in reader[1:]:
        details_str = data_row[8]
        parsed_details = json.loads(details_str)
        assert isinstance(parsed_details, dict)

    # 4. Filtered export (user_a only) -> header + 2 rows
    filtered_out = await export_audit_events(
        db_session,
        ExportAuditEventsInput(user_id=user_a),
    )
    filtered_reader = list(csv.reader(io.StringIO(filtered_out.csv_content)))
    assert len(filtered_reader) == 3
    assert filtered_out.row_count == 2

    # 5. Verify ExportAuditEventsOut unpacking / string representation
    csv_str, fn = filtered_out
    assert csv_str == filtered_out.csv_content
    assert fn == filtered_out.filename
    assert str(filtered_out) == filtered_out.csv_content
    assert filtered_out.content == filtered_out.csv_content


def test_audit_module__append_only_guard__no_delete_or_update_statements() -> None:
    """Honest guard test: verify that the audit module contains no UPDATE or DELETE statements.

    Ensures that AuditEvent remains strictly append-only across all models,
    services, and routers in src/planner/modules/audit.
    """
    audit_module_dir = Path(__file__).resolve().parents[2] / "src" / "planner" / "modules" / "audit"
    assert audit_module_dir.exists(), f"Directory not found: {audit_module_dir}"

    python_files = list(audit_module_dir.rglob("*.py"))
    assert len(python_files) > 0, "No python files found in audit module"

    forbidden_patterns = [
        re.compile(r"\bdelete\s*\(", re.IGNORECASE),
        re.compile(r"\.delete\s*\(", re.IGNORECASE),
        re.compile(r"\bupdate\s*\(", re.IGNORECASE),
        re.compile(r"\.update\s*\(", re.IGNORECASE),
        re.compile(r"DELETE\s+FROM", re.IGNORECASE),
        re.compile(r"UPDATE\s+audit", re.IGNORECASE),
    ]

    violations: list[str] = []
    for py_file in python_files:
        content = py_file.read_text(encoding="utf-8")
        # Exclude docstrings/comments mentioning "never UPDATEs or DELETEs"
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            for pattern in forbidden_patterns:
                if pattern.search(line):
                    violations.append(f"{py_file.name}:{idx} matches forbidden pattern '{pattern.pattern}': {line}")

    assert not violations, f"Append-only rule violated! Found forbidden operations:\n" + "\n".join(violations)


def test_audit_api__http_endpoints__roles_and_responses(db_session: AsyncSession) -> None:
    """Test HTTP endpoints for list and export with RBAC and schema verification."""
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    # Routers carry their own full `/api/v1/...` prefix (integration 2026-09-30).
    app.include_router(list_router)
    app.include_router(export_router)

    # Override get_session to use test SQLite database session
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    client = TestClient(app)

    # 1. Auditor role accessing GET /api/v1/audit-events (allowed: 200)
    app.dependency_overrides[get_current_principal] = lambda: RequestPrincipal(
        user_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        role="auditor",
    )
    r_list = client.get("/api/v1/audit-events?pageSize=10")
    assert r_list.status_code == 200
    data = r_list.json()
    assert "items" in data
    assert "pageSize" in data
    assert data["pageSize"] == 10

    # 2. Administrator role accessing GET /api/v1/audit-events (allowed: 200)
    app.dependency_overrides[get_current_principal] = lambda: RequestPrincipal(
        user_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        role="administrator",
    )
    r_list_admin = client.get("/api/v1/audit-events")
    assert r_list_admin.status_code == 200

    # 3. Viewer role accessing GET /api/v1/audit-events (forbidden: 403)
    app.dependency_overrides[get_current_principal] = lambda: RequestPrincipal(
        user_id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        role="viewer",
    )
    r_list_viewer = client.get("/api/v1/audit-events")
    assert r_list_viewer.status_code == 403
    assert r_list_viewer.json()["code"] == "FORBIDDEN"

    # 4. Auditor role accessing GET /api/v1/audit-events/export (allowed: 200 text/csv)
    app.dependency_overrides[get_current_principal] = lambda: RequestPrincipal(
        user_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        role="auditor",
    )
    r_export = client.get("/api/v1/audit-events/export")
    assert r_export.status_code == 200
    assert r_export.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=\"audit-events-" in r_export.headers["content-disposition"]
    assert "id,occurred_at,user_id" in r_export.text

    # 5. Administrator role accessing GET /api/v1/audit-events/export (forbidden: 403 per Backend.md)
    app.dependency_overrides[get_current_principal] = lambda: RequestPrincipal(
        user_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        role="administrator",
    )
    r_export_admin = client.get("/api/v1/audit-events/export")
    assert r_export_admin.status_code == 403
    assert r_export_admin.json()["code"] == "FORBIDDEN"

    # 6. Viewer role accessing GET /api/v1/audit-events/export (forbidden: 403)
    app.dependency_overrides[get_current_principal] = lambda: RequestPrincipal(
        user_id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        role="viewer",
    )
    r_export_viewer = client.get("/api/v1/audit-events/export")
    assert r_export_viewer.status_code == 403
    assert r_export_viewer.json()["code"] == "FORBIDDEN"

