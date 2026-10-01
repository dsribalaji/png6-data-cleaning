from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import openpyxl
import polars as pl


@dataclass
class QuarantinedRow:
    row_ref: str  # source row number as the user sees it, e.g. "row 7" (header is row 1)
    reason: str
    cells: list[str]


@dataclass
class IngestResult:
    table: pl.DataFrame
    quarantined: pl.DataFrame
    warnings: list[str]
    stats: dict[str, Any]
    quarantine: list[QuarantinedRow] = field(default_factory=list)


def _is_cell_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _is_row_empty(row: list[Any] | tuple[Any, ...]) -> bool:
    return all(_is_cell_empty(c) for c in row)


def _malformed_reason(row: list[Any], header_width: int) -> str | None:
    """Why a row cannot be parsed against the header, or None if it can (FR-044).

    Generic rules only (FR-050): a row is malformed when it has data beyond the
    header (a shifted or ragged row) or text that failed to decode. A missing
    value is NOT malformed; it stays in the table as null.
    """
    extra = [c for c in row[header_width:] if not _is_cell_empty(c)]
    if extra:
        return f"Row has {len(extra)} more cell(s) than the header has columns"
    if any(isinstance(c, str) and "\ufffd" in c for c in row):
        return "Row contains characters that could not be decoded"
    return None


def _process_tabular_data(
    raw_header: list[Any],
    raw_data: list[list[Any]],
) -> IngestResult:
    # Header width = up to the last named column; columns after it have no header,
    # so any data found there means the row is shifted.
    named = [i for i, h in enumerate(raw_header) if not _is_cell_empty(h)]
    header_width = named[-1] + 1 if named else len(raw_header)

    # 1. Drop fully-null rows (padding rows); quarantine malformed rows (FR-044)
    data_rows: list[list[Any]] = []
    quarantine: list[QuarantinedRow] = []
    padding_rows_dropped = 0
    for idx, r in enumerate(raw_data):
        if _is_row_empty(r):
            padding_rows_dropped += 1
            continue
        reason = _malformed_reason(list(r), header_width)
        if reason:
            cells = ["" if _is_cell_empty(c) else str(c) for c in r]
            quarantine.append(QuarantinedRow(row_ref=f"row {idx + 2}", reason=reason, cells=cells))
        else:
            data_rows.append(list(r))

    # 2. Retain named columns, and unnamed columns inside the header that hold data
    retained_col_indices: list[int] = []
    for c_idx in range(header_width):
        h_empty = _is_cell_empty(raw_header[c_idx])
        col_all_empty = all(_is_cell_empty(r[c_idx]) if c_idx < len(r) else True for r in data_rows)
        if not (h_empty and col_all_empty):
            retained_col_indices.append(c_idx)

    empty_columns_dropped = len(raw_header) - len(retained_col_indices)

    # 3. Clean headers for retained columns
    headers: list[str] = []
    for out_idx, c_idx in enumerate(retained_col_indices):
        h = raw_header[c_idx]
        if _is_cell_empty(h):
            headers.append(f"unnamed_{out_idx}")
        else:
            headers.append(str(h).strip())

    # 4. Filter cells to retained columns
    table_rows = [
        [r[c_idx] if c_idx < len(r) else None for c_idx in retained_col_indices] for r in data_rows
    ]

    # 5. Build Polars DataFrames
    warnings: list[str] = []
    if table_rows:
        table_df = pl.DataFrame(table_rows, schema=headers, orient="row")
    else:
        table_df = pl.DataFrame({h: [] for h in headers})

    if quarantine:
        width = max(len(q.cells) for q in quarantine)
        quarantined_df = pl.DataFrame(
            {
                "row_ref": [q.row_ref for q in quarantine],
                "reason": [q.reason for q in quarantine],
                **{
                    f"cell_{i + 1}": [q.cells[i] if i < len(q.cells) else "" for q in quarantine]
                    for i in range(width)
                },
            }
        )
        warnings.append(f"{len(quarantine)} malformed row(s) quarantined")
    else:
        quarantined_df = pl.DataFrame()

    # 6. Check sparse columns (>= 95% nulls) and warnings
    sparse_columns: list[str] = []
    total_table_rows = len(table_df)

    if total_table_rows > 0:
        for col_name in table_df.columns:
            null_count = table_df[col_name].null_count()
            null_pct = null_count / total_table_rows
            if null_pct >= 0.95:
                sparse_columns.append(col_name)
                warnings.append(
                    f"Column '{col_name}' has {null_pct * 100:.1f}% nulls "
                    f"({null_count}/{total_table_rows} rows)"
                )

    stats: dict[str, Any] = {
        "row_count": len(table_df),
        "column_count": len(table_df.columns),
        "padding_rows_dropped": padding_rows_dropped,
        "empty_columns_dropped": empty_columns_dropped,
        "sparse_columns": sparse_columns,
        "quarantined_rows": len(quarantine),
    }

    return IngestResult(
        table=table_df,
        quarantined=quarantined_df,
        warnings=warnings,
        stats=stats,
        quarantine=quarantine,
    )


def read_workbook(path: str | Path, sheet: str | int = 0) -> IngestResult:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if isinstance(sheet, int):
            ws = wb.worksheets[sheet]
        else:
            ws = wb[sheet]

        all_rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    if not all_rows:
        empty_df = pl.DataFrame()
        return IngestResult(
            table=empty_df,
            quarantined=empty_df,
            warnings=[],
            stats={
                "row_count": 0,
                "column_count": 0,
                "padding_rows_dropped": 0,
                "empty_columns_dropped": 0,
                "sparse_columns": [],
            },
        )

    raw_header = list(all_rows[0])
    raw_data = [list(r) for r in all_rows[1:]]

    return _process_tabular_data(raw_header, raw_data)


def read_csv(path: str | Path) -> IngestResult:
    path_obj = Path(path)
    with path_obj.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        all_rows = list(reader)

    if not all_rows:
        empty_df = pl.DataFrame()
        return IngestResult(
            table=empty_df,
            quarantined=empty_df,
            warnings=[],
            stats={
                "row_count": 0,
                "column_count": 0,
                "padding_rows_dropped": 0,
                "empty_columns_dropped": 0,
                "sparse_columns": [],
            },
        )

    raw_header = all_rows[0]
    raw_data = all_rows[1:]

    # In CSV, convert empty strings to None for proper null handling
    converted_data: list[list[Any]] = []
    for r in raw_data:
        converted_data.append([None if _is_cell_empty(c) else c for c in r])

    return _process_tabular_data(raw_header, converted_data)
