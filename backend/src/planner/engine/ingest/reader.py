from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openpyxl
import polars as pl


@dataclass
class IngestResult:
    table: pl.DataFrame
    quarantined: pl.DataFrame
    warnings: list[str]
    stats: dict[str, Any]


def _is_cell_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _is_row_empty(row: list[Any] | tuple[Any, ...]) -> bool:
    return all(_is_cell_empty(c) for c in row)


def _process_tabular_data(
    raw_header: list[Any],
    raw_data: list[list[Any]],
    is_reference_dataset: bool = False,
) -> IngestResult:
    # 1. Drop fully-null rows (padding rows)
    data_rows: list[list[Any]] = []
    padding_rows_dropped = 0
    for r in raw_data:
        if _is_row_empty(r):
            padding_rows_dropped += 1
        else:
            data_rows.append(list(r))

    # 2. Identify fully-null columns (header empty AND all data values empty)
    num_cols = len(raw_header)
    empty_col_indices: set[int] = set()
    retained_col_indices: list[int] = []

    for c_idx in range(num_cols):
        h = raw_header[c_idx]
        h_empty = _is_cell_empty(h)
        col_all_empty = all(
            _is_cell_empty(r[c_idx]) if c_idx < len(r) else True for r in data_rows
        )
        if h_empty and col_all_empty:
            empty_col_indices.add(c_idx)
        else:
            retained_col_indices.append(c_idx)

    empty_columns_dropped = len(empty_col_indices)

    # 3. Clean headers for retained columns
    headers: list[str] = []
    for out_idx, c_idx in enumerate(retained_col_indices):
        h = raw_header[c_idx]
        if _is_cell_empty(h):
            headers.append(f"unnamed_{out_idx}")
        else:
            headers.append(str(h).strip())

    # 4. Filter cells to retained columns and identify quarantined rows
    table_rows: list[list[Any]] = []
    quarantined_rows: list[list[Any]] = []

    for r in data_rows:
        filtered_row = [r[c_idx] if c_idx < len(r) else None for c_idx in retained_col_indices]
        first_cell = filtered_row[0] if filtered_row else None
        first_is_empty = _is_cell_empty(first_cell)
        has_other_data = any(not _is_cell_empty(c) for c in filtered_row[1:])

        if not is_reference_dataset and first_is_empty and has_other_data:
            quarantined_rows.append(filtered_row)
        else:
            table_rows.append(filtered_row)

    # 5. Build Polars DataFrames
    if table_rows:
        table_df = pl.DataFrame(table_rows, schema=headers, orient="row")
    else:
        table_df = pl.DataFrame({h: [] for h in headers})

    if quarantined_rows:
        quarantined_df = pl.DataFrame(quarantined_rows, schema=headers, orient="row")
    else:
        quarantined_df = pl.DataFrame([], schema=table_df.schema)

    # 6. Check sparse columns (>= 95% nulls) and warnings
    warnings: list[str] = []
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
    }

    return IngestResult(
        table=table_df,
        quarantined=quarantined_df,
        warnings=warnings,
        stats=stats,
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

    path_obj = Path(path)
    is_ref = "vendorinvoices" in path_obj.name.lower() or (
        len(raw_header) >= 14
        and str(raw_header[0]).strip() == "invoice_date"
        and str(raw_header[1]).strip() == "invoice_number"
        and str(raw_header[3]).strip() == "supplier_name"
    )

    return _process_tabular_data(raw_header, raw_data, is_reference_dataset=is_ref)


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

    is_ref = "vendorinvoices" in path_obj.name.lower() or (
        len(raw_header) >= 14
        and str(raw_header[0]).strip() == "invoice_date"
        and str(raw_header[1]).strip() == "invoice_number"
        and str(raw_header[3]).strip() == "supplier_name"
    )

    # In CSV, convert empty strings to None for proper null handling
    converted_data: list[list[Any]] = []
    for r in raw_data:
        converted_data.append([None if _is_cell_empty(c) else c for c in r])

    return _process_tabular_data(raw_header, converted_data, is_reference_dataset=is_ref)
