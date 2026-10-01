"""Storage-aware ingest entry point (integration 2026-09-30).

Bridges the datasets module (which stores the raw upload in the configured
storage backend and calls ``ingest_dataset_file(raw_object_key)``) with the
W2 engine readers (which work on local file paths).

Flow: download raw bytes -> read into a Polars frame -> write Parquet ->
upload Parquet back to storage under ``ingested/...``.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from planner.engine.ingest.parquet import to_parquet
from planner.engine.ingest.reader import read_csv, read_workbook


@dataclass
class DatasetIngestResult:
    """What the datasets ingest task needs from engine ingest."""

    row_count: int
    column_count: int
    ingested_object_key: str
    warnings: list[str]
    # FR-044: rows that could not be parsed, as (row_ref, reason); saved to
    # quarantine/<dataset_id>.parquet so nothing is dropped silently.
    quarantine: list[tuple[str, str]] = field(default_factory=list)


async def ingest_dataset_file(raw_object_key: str) -> DatasetIngestResult:
    """Ingest a raw upload from storage into a queryable Parquet object.

    Args:
        raw_object_key: storage key of the uploaded file,
            e.g. ``raw/<dataset_id>/VendorInvoices_uncleaned.xlsx``.

    Returns:
        DatasetIngestResult with row/column counts and the Parquet key.
    """
    # Lazy import: execution.public pulls in module machinery; the engine
    # must not import it at module load time (circular import risk).
    from planner.modules.execution.public import get_storage

    storage = get_storage()
    raw_bytes = await storage.get(raw_object_key)

    suffix = Path(raw_object_key).suffix.lower()
    # raw/<dataset_id>/<file> -> ingested/<dataset_id>/<file>.parquet
    parts = raw_object_key.split("/")
    if len(parts) >= 3 and parts[0] == "raw":
        dataset_id = parts[1]
        stem = Path(parts[-1]).stem
    else:  # pragma: no cover - defensive; keys always follow the convention
        dataset_id = "unknown"
        stem = Path(raw_object_key).stem
    ingested_key = f"ingested/{dataset_id}/{stem}.parquet"

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = os.path.join(tmpdir, f"raw{suffix or '.bin'}")
        with open(raw_path, "wb") as fh:
            fh.write(raw_bytes)

        if suffix == ".csv":
            result = read_csv(raw_path)
        else:
            # .xlsx/.xls/.xlsm and anything else -> workbook reader
            result = read_workbook(raw_path)

        parquet_path = os.path.join(tmpdir, "ingested.parquet")
        to_parquet(result.table, parquet_path)
        with open(parquet_path, "rb") as fh:
            parquet_bytes = fh.read()

        quarantine_bytes = None
        if result.quarantine:
            q_path = os.path.join(tmpdir, "quarantine.parquet")
            to_parquet(result.quarantined, q_path)
            with open(q_path, "rb") as fh:
                quarantine_bytes = fh.read()

    await storage.put(ingested_key, parquet_bytes, content_type="application/octet-stream")
    if quarantine_bytes is not None:
        await storage.put(
            f"quarantine/{dataset_id}.parquet",
            quarantine_bytes,
            content_type="application/octet-stream",
        )

    return DatasetIngestResult(
        row_count=result.table.height,
        column_count=result.table.width,
        ingested_object_key=ingested_key,
        warnings=list(result.warnings),
        quarantine=[(q.row_ref, q.reason) for q in result.quarantine],
    )
