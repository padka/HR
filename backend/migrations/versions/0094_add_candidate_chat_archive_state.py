"""Add archive state for candidate chat threads."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, table_exists

revision = "0094_add_candidate_chat_archive_state"
down_revision = "0093_reschedule_windows_and_candidate_chat_reads"
branch_labels = None
depends_on = None


def _rebuild_candidate_chat_reads_sqlite(conn: Connection, *, downgrade: bool = False) -> None:
    archived_column = "" if downgrade else ", archived_at TIMESTAMP"
    archived_select = "" if downgrade else ", archived_at"
    archived_insert = "" if downgrade else ", archived_at"

    conn.execute(sa.text("PRAGMA foreign_keys=OFF"))
    try:
        conn.execute(sa.text("ALTER TABLE candidate_chat_reads RENAME TO candidate_chat_reads_old"))
        conn.execute(
            sa.text(
                f"""
                CREATE TABLE candidate_chat_reads (
                    id INTEGER PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    principal_type TEXT NOT NULL,
                    principal_id INTEGER NOT NULL,
                    last_read_at TIMESTAMP
                    {archived_column},
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            sa.text(
                f"""
                INSERT INTO candidate_chat_reads (
                    id,
                    candidate_id,
                    principal_type,
                    principal_id,
                    last_read_at
                    {archived_insert},
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    candidate_id,
                    principal_type,
                    principal_id,
                    last_read_at
                    {archived_select},
                    created_at,
                    updated_at
                FROM candidate_chat_reads_old
                """
            )
        )
        conn.execute(sa.text("DROP TABLE candidate_chat_reads_old"))
        conn.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS ix_candidate_chat_reads_principal
                ON candidate_chat_reads (principal_type, principal_id, last_read_at)
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_chat_reads_principal
                ON candidate_chat_reads (candidate_id, principal_type, principal_id)
                """
            )
        )
    finally:
        conn.execute(sa.text("PRAGMA foreign_keys=ON"))


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "candidate_chat_reads"):
        return
    if column_exists(conn, "candidate_chat_reads", "archived_at"):
        return

    if conn.dialect.name == "sqlite":
        _rebuild_candidate_chat_reads_sqlite(conn)
        return

    conn.execute(
        sa.text(
            "ALTER TABLE candidate_chat_reads "
            "ADD COLUMN archived_at TIMESTAMP WITH TIME ZONE"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if not table_exists(conn, "candidate_chat_reads"):
        return
    if not column_exists(conn, "candidate_chat_reads", "archived_at"):
        return

    if conn.dialect.name == "sqlite":
        _rebuild_candidate_chat_reads_sqlite(conn, downgrade=True)
        return

    conn.execute(
        sa.text(
            "ALTER TABLE candidate_chat_reads "
            "DROP COLUMN archived_at"
        )
    )
