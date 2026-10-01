"""0004 datasets ingested_object_key

Revision ID: 3f4c9c838b34
Revises: cced014e9c3a
Create Date: 2026-09-30

Adds datasets.ingested_object_key: the Parquet object written by engine
ingest, read back by profiling/execution. The model referenced it but the
column was never created (integration 2026-09-30).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3f4c9c838b34"
down_revision: str | Sequence[str] | None = "cced014e9c3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema() -> str | None:
    """The table lives in schema "datasets" on PostgreSQL; SQLite has one namespace."""
    return "datasets" if op.get_bind().dialect.name == "postgresql" else None


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column("ingested_object_key", sa.Text(), nullable=True),
        schema=_schema(),
    )


def downgrade() -> None:
    op.drop_column("datasets", "ingested_object_key", schema=_schema())
