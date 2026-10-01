"""0005 AI status on profile runs and plans; flagged cells on profile runs

Revision ID: 0005_ai_status
Revises: 3f4c9c838b34
Create Date: 2026-10-01

Level 3 M2 (docs/LEVEL3_PLAN.md B2, C4):
- ai_status / ai_message: whether AI suggestions were used for this profile or
  plan ("used"), unavailable because no model is configured ("off"), or failed
  ("failed", with a message). A failure no longer disappears silently.
- plan_steps.source: "deterministic" or "llm", so the UI can tag AI suggestions.
- profile_runs.flagged_cells: cells the prompt-injection guard flagged (FR-045),
  shown to the user and never sent to a model.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_ai_status"
down_revision: str | Sequence[str] | None = "3f4c9c838b34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema(name: str) -> str | None:
    """Module schemas exist on PostgreSQL; SQLite has one namespace."""
    return name if op.get_bind().dialect.name == "postgresql" else None


def upgrade() -> None:
    for table, schema in (("profile_runs", "profiling"), ("plans", "planning")):
        op.add_column(table, sa.Column("ai_status", sa.String(20), nullable=True), schema=_schema(schema))
        op.add_column(table, sa.Column("ai_message", sa.Text(), nullable=True), schema=_schema(schema))
    op.add_column(
        "profile_runs",
        sa.Column("flagged_cells", sa.JSON(), nullable=True),
        schema=_schema("profiling"),
    )
    op.add_column(
        "plan_steps",
        sa.Column("source", sa.String(20), nullable=False, server_default="deterministic"),
        schema=_schema("planning"),
    )


def downgrade() -> None:
    op.drop_column("plan_steps", "source", schema=_schema("planning"))
    op.drop_column("profile_runs", "flagged_cells", schema=_schema("profiling"))
    for table, schema in (("profile_runs", "profiling"), ("plans", "planning")):
        op.drop_column(table, "ai_message", schema=_schema(schema))
        op.drop_column(table, "ai_status", schema=_schema(schema))
