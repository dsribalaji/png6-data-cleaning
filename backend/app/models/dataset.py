"""Dataset, ColumnProfile, and Quarantine database models."""

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk


class Dataset(Base, UUIDPk):
    """Dataset metadata record.

    FR-004: Originals are immutable by design. The storage_key references the
    untouched source file in MinIO; all transformations are executed on a working copy.
    """

    __tablename__ = "datasets"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # MinIO key of the IMMUTABLE original (FR-004)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    col_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Status: uploaded / profiled / planned / executed / rolled_back
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="uploaded")
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class ColumnProfile(Base, UUIDPk):
    """Column profiling statistics and semantic flags.

    Flags map directly to observed issue labels:
    - all_null -> `all-null-columns`
    - embedded_json -> `json-buried-line-items`
    - currency_text -> `dollar-text-in-json`
    - float_artifact -> `float-artifacts`
    - invalid_gstin -> `invalid-9char-gstin`
    - missing_dates_pos -> `missing-dates-pos`
    - padding_row -> `padding-rows`
    - supplier_variant -> `supplier-variants-7-to-5`
    - redundant_total_price -> `redundant-total-price`
    """

    __tablename__ = "column_profiles"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dtype: Mapped[str] = mapped_column(String(50), nullable=False)
    null_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    null_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    distinct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class QuarantineRecord(Base, UUIDPk):
    """Quarantined unparseable row or flagged poisoned-cell record.

    FR-044: Quarantine unparseable rows and continue execution; flag poisoned
    cells (e.g. prompt-injection attempts aimed at downstream LLMs).
    """

    __tablename__ = "quarantine_records"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False, index=True
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
