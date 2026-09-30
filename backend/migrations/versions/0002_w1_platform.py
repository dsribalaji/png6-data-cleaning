"""W1 platform slice: users, datasets schemas + public.outbox.

Revision ID: 0002_w1_platform
Revises: 0001
Create Date: 2026-09-30

Mirrors the SQLAlchemy models in:
- src/planner/modules/users/models.py (schema "users" on PostgreSQL)
- src/planner/modules/datasets/models.py (schema "datasets" on PostgreSQL)
- src/planner/core/outbox.py (public.outbox)

PostgreSQL gets real schemas ("users", "datasets"); SQLite keeps all tables
in the default namespace (schema_for() returns None there).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_w1_platform"
down_revision = "0001"
branch_labels = None
depends_on = None

_USERS = "users"
_DATASETS = "datasets"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _sch(name: str) -> str | None:
    return name if _is_postgres() else None


def upgrade() -> None:
    if _is_postgres():
        op.execute(sa.schema.CreateSchema(_USERS, if_not_exists=True))
        op.execute(sa.schema.CreateSchema(_DATASETS, if_not_exists=True))

    users_sch = _sch(_USERS)
    datasets_sch = _sch(_DATASETS)

    # ---- users schema ---------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="invited"),
        sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('invited', 'active', 'deactivated')",
            name="ck_users_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        schema=users_sch,
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('data_engineer', 'administrator', 'auditor', 'viewer')",
            name="ck_user_roles_role",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{users_sch + '.' if users_sch else ''}users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("user_id"),
        schema=users_sch,
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{users_sch + '.' if users_sch else ''}users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        schema=users_sch,
    )
    op.create_index(
        "ix_refresh_tokens_family_id",
        "refresh_tokens",
        ["family_id"],
        schema=users_sch,
    )

    op.create_table(
        "invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('data_engineer', 'administrator', 'auditor', 'viewer')",
            name="ck_invites_role",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        schema=users_sch,
    )

    # ---- datasets schema ------------------------------------------------
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("column_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="profiling"),
        sa.Column("raw_object_key", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source IN ('upload', 'n8n_folder')",
            name="ck_datasets_source",
        ),
        sa.CheckConstraint(
            "status IN ('profiling', 'profiled', 'plan_ready', 'approved', 'executed', "
            "'tests_failed', 'rolled_back', 'failed')",
            name="ck_datasets_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        schema=datasets_sch,
    )

    op.create_table(
        "quarantine_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("row_ref", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            [f"{datasets_sch + '.' if datasets_sch else ''}datasets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=datasets_sch,
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column(
            "progress_pct", sa.Float(), nullable=False, server_default="0.0"
        ),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_jobs_status",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            [f"{datasets_sch + '.' if datasets_sch else ''}datasets.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=datasets_sch,
    )

    # ---- public.outbox --------------------------------------------------
    op.create_table(
        "outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outbox_published_at_null",
        "outbox",
        ["published_at"],
        postgresql_where=sa.text("published_at IS NULL"),
        sqlite_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    users_sch = _sch(_USERS)
    datasets_sch = _sch(_DATASETS)

    op.drop_index(
        "ix_outbox_published_at_null",
        table_name="outbox",
        postgresql_where=sa.text("published_at IS NULL"),
        sqlite_where=sa.text("published_at IS NULL"),
    )
    op.drop_table("outbox")

    op.drop_table("jobs", schema=datasets_sch)
    op.drop_table("quarantine_records", schema=datasets_sch)
    op.drop_table("datasets", schema=datasets_sch)

    op.drop_table("invites", schema=users_sch)
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens", schema=users_sch)
    op.drop_table("refresh_tokens", schema=users_sch)
    op.drop_table("user_roles", schema=users_sch)
    op.drop_table("users", schema=users_sch)

    if _is_postgres():
        op.execute(sa.schema.DropSchema(_DATASETS))
        op.execute(sa.schema.DropSchema(_USERS))
