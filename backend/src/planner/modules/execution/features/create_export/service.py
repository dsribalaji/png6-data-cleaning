"""Service for creating dataset exports."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from uuid import UUID
import uuid

import openpyxl
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.errors import AppError
from planner.modules.execution.errors import ExecutionErrors
from planner.modules.execution.models import ExportRow
from planner.modules.execution.schemas import ExportRequest, ExportResponse


async def create_export(
    session: AsyncSession,
    plan_id: UUID,
    req: ExportRequest,
    actor_id: UUID | None = None,
) -> ExportResponse:
    """Export the current executed version of a dataset to xlsx or csv.

    CSV format exports ONLY the main table.
    XLSX format includes the main table and side tables as separate sheets.
    """
    fmt = req.format.lower()
    if fmt not in ("xlsx", "csv"):
        raise AppError("INVALID_FORMAT", "Format must be xlsx or csv.", 400)

    from planner.modules.execution.public import (
        get_current_version_no,
        get_storage,
        list_side_tables,
        read_snapshot_frame,
    )

    current = await get_current_version_no(session, plan_id)
    if current <= 0:
        raise ExecutionErrors.NO_EXECUTED_VERSION

    # Validation gate: export is blocked if latest validation did not pass
    try:
        from planner.modules.validation.public import latest_validation_passed

        validation_passed = await latest_validation_passed(session, plan_id, current)
    except (ImportError, AttributeError):
        validation_passed = False

    if not validation_passed:
        raise ExecutionErrors.EXPORT_BLOCKED_TESTS_FAILED

    df = await read_snapshot_frame(plan_id, current)
    storage = get_storage()

    if fmt == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "main"
        ws.append(list(df.columns))
        for row in df.iter_rows():
            ws.append(list(row))

        side_tables = await list_side_tables(plan_id, current)
        for table_name, side_df in side_tables.items():
            sheet_title = table_name[:31]  # Excel worksheet title max length
            sws = wb.create_sheet(title=sheet_title)
            sws.append(list(side_df.columns))
            for row in side_df.iter_rows():
                sws.append(list(row))

        buf = io.BytesIO()
        wb.save(buf)
        data = buf.getvalue()
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        object_key = f"exports/{plan_id}/v{current}/main.xlsx"
    else:  # csv
        data = df.write_csv().encode("utf-8")
        content_type = "text/csv"
        object_key = f"exports/{plan_id}/v{current}/main.csv"

    await storage.put_object(object_key, data, content_type)
    download_url = await storage.presigned_get_url(object_key, expires_seconds=900)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=900)

    export_row = ExportRow(
        id=uuid.uuid4(),
        plan_id=plan_id,
        version_no=current,
        format=fmt,
        object_key=object_key,
        exported_by=actor_id,
    )
    session.add(export_row)
    await session.commit()

    return ExportResponse(download_url=download_url, expires_at=expires_at)
