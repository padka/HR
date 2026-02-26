"""Add recruiter calendar tasks table for manual planning."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import index_exists, table_exists

revision = "0082_add_calendar_tasks"
down_revision = "0081_add_detailization_soft_delete"
branch_labels = None
depends_on = None

TABLE = "calendar_tasks"
IDX_RECRUITER_START = "ix_calendar_tasks_recruiter_start"
IDX_START_END = "ix_calendar_tasks_start_end"


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, TABLE):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    f"""
                    CREATE TABLE {TABLE} (
                        id INTEGER PRIMARY KEY,
                        recruiter_id INTEGER NOT NULL REFERENCES recruiters(id) ON DELETE CASCADE,
                        title VARCHAR(180) NOT NULL,
                        description TEXT NULL,
                        start_utc TIMESTAMP WITH TIME ZONE NOT NULL,
                        end_utc TIMESTAMP WITH TIME ZONE NOT NULL,
                        is_done BOOLEAN NOT NULL DEFAULT FALSE,
                        created_by_type VARCHAR(16) NOT NULL DEFAULT 'recruiter',
                        created_by_id INTEGER NULL,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    f"""
                    CREATE TABLE {TABLE} (
                        id SERIAL PRIMARY KEY,
                        recruiter_id INTEGER NOT NULL REFERENCES recruiters(id) ON DELETE CASCADE,
                        title VARCHAR(180) NOT NULL,
                        description TEXT NULL,
                        start_utc TIMESTAMPTZ NOT NULL,
                        end_utc TIMESTAMPTZ NOT NULL,
                        is_done BOOLEAN NOT NULL DEFAULT FALSE,
                        created_by_type VARCHAR(16) NOT NULL DEFAULT 'recruiter',
                        created_by_id INTEGER NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )

    # Ensure PostgreSQL sequence/default exists even when table was already created
    # by an earlier buggy migration revision.
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(f"CREATE SEQUENCE IF NOT EXISTS {TABLE}_id_seq"))
        conn.execute(
            sa.text(
                f"ALTER TABLE {TABLE} ALTER COLUMN id SET DEFAULT nextval('{TABLE}_id_seq')"
            )
        )
        conn.execute(
            sa.text(
                f"""
                SELECT setval(
                    '{TABLE}_id_seq',
                    COALESCE((SELECT MAX(id) FROM {TABLE}), 1),
                    (SELECT COUNT(*) > 0 FROM {TABLE})
                )
                """
            )
        )

    if not index_exists(conn, TABLE, IDX_RECRUITER_START):
        conn.execute(
            sa.text(
                f"CREATE INDEX IF NOT EXISTS {IDX_RECRUITER_START} ON {TABLE} (recruiter_id, start_utc)"
            )
        )

    if not index_exists(conn, TABLE, IDX_START_END):
        conn.execute(
            sa.text(
                f"CREATE INDEX IF NOT EXISTS {IDX_START_END} ON {TABLE} (start_utc, end_utc)"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {IDX_START_END}"))
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {IDX_RECRUITER_START}"))
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {TABLE}"))
