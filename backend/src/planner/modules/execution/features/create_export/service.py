"""Service for creating dataset exports."""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from uuid import UUID

import openpyxl
import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession

from planner.core.audit import record_audit
from planner.core.errors import AppError
from planner.modules.execution.errors import ExecutionErrors
from planner.modules.execution.models import ExportRow
from planner.modules.execution.schemas import ExportRequest, ExportResponse

# C5 / OWASP CSV injection: text a spreadsheet would run as a formula gets a leading
# apostrophe. A leading "-" is left alone when the cell is just a number ("-12.5").
_FORMULA_START = r"^[=+@\t\r]|^-[^0-9.]"


def neutralise_formulas(frame: pl.DataFrame) -> pl.DataFrame:
    """Return the frame with formula-like text cells made inert for Excel/CSV."""
    text_cols = [c for c, t in frame.schema.items() if t == pl.Utf8]
    return frame.with_columns(
        pl.when(pl.col(c).str.contains(_FORMULA_START))
        .then(pl.lit("'") + pl.col(c))
        .otherwise(pl.col(c))
        .alias(c)
        for c in text_cols
    )

async def create_export(
    session: AsyncSession,
    plan_id: UUID,
    req: ExportRequest,
    actor_id: UUID | None = None,
) -> ExportResponse:
    """Export the current version: xlsx (one sheet per table), csv (zip, one file per
    table) or pipeline (JSON list of the executed catalogue operations)."""
    fmt = req.format.lower()
    if fmt not in ("xlsx", "csv", "pipeline"):
        raise AppError("INVALID_FORMAT", "Format must be xlsx, csv or pipeline.", 400)

    from planner.modules.execution.public import (
        get_current_version_no,
        get_storage,
        list_side_tables,
        read_snapshot_frame,
    )

    current = await get_current_version_no(session, plan_id)
    if current <= 0:
        raise ExecutionErrors.NO_EXECUTED_VERSION

    # Validation gate (FR-043): export is blocked if latest validation did not pass
    try:
        from planner.modules.validation.public import latest_validation_passed

        validation_passed = await latest_validation_passed(session, plan_id, current)
    except (ImportError, AttributeError):
        validation_passed = False

    if not validation_passed:
        raise ExecutionErrors.EXPORT_BLOCKED_TESTS_FAILED

    storage = get_storage()
    base = f"exports/{plan_id}/v{current}"

    if fmt == "pipeline":
        # FR-037: re-runnable definition = the executed catalogue ops, in order.
        from planner.modules.planning.public import get_decided_steps

        steps = await get_decided_steps(session, plan_id)
        definition = {
            "schemaVersion": 1,
            "planId": str(plan_id),
            "versionNo": current,
            "steps": [
                {"stepNo": st["step_no"], "operation": st["operation"], "parameters": st["parameters"]}
                for st in steps
            ],
        }
        data = json.dumps(definition, indent=2).encode("utf-8")
        content_type = "application/json"
        object_key = f"{base}/pipeline.json"
    else:
        tables = {"main": await read_snapshot_frame(plan_id, current)}
        tables.update(await list_side_tables(plan_id, current))
        tables = {name: neutralise_formulas(frame) for name, frame in tables.items()}
        if fmt == "xlsx":
            wb = openpyxl.Workbook()
            wb.remove(wb.active)
            for table_name, frame in tables.items():
                ws = wb.create_sheet(title=table_name[:31])  # Excel sheet title max 31
                ws.append(list(frame.columns))
                for row in frame.iter_rows():
                    ws.append(list(row))
            buf = io.BytesIO()
            wb.save(buf)
            data = buf.getvalue()
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            object_key = f"{base}/tables.xlsx"
        elif req.table:  # csv of one table
            if req.table not in tables:
                raise ExecutionErrors.TABLE_NOT_FOUND
            data = tables[req.table].write_csv().encode("utf-8")
            content_type = "text/csv"
            object_key = f"{base}/{req.table}.csv"
        else:  # csv: one file per table, zipped
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for table_name, frame in tables.items():
                    zf.writestr(f"{table_name}.csv", frame.write_csv())
            data = buf.getvalue()
            content_type = "application/zip"
            object_key = f"{base}/tables.csv.zip"

    await storage.put_object(object_key, data, content_type)
    download_url = await storage.presigned_get_url(object_key, expires_seconds=900)
    now = datetime.now(UTC)
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
    await record_audit(
        session=session,
        user_id=actor_id,
        event_type="plan.exported",
        object_type="plan",
        object_id=str(plan_id),
        details={"format": fmt, "versionNo": current, "objectKey": object_key},
    )
    await session.commit()

    return ExportResponse(download_url=download_url, expires_at=expires_at)
