"""Add shared workspace state for candidate chat threads."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import index_exists, table_exists

revision = "0096_add_candidate_chat_workspaces"
down_revision = "0095_add_candidate_portal_journey"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "candidate_chat_workspaces"):
        conn.execute(
            sa.text(
                """
                CREATE TABLE candidate_chat_workspaces (
                    id INTEGER PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    shared_note TEXT,
                    agreements_json JSON,
                    follow_up_due_at TIMESTAMP,
                    updated_by VARCHAR(160),
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
            )
        )
    if not index_exists(conn, "candidate_chat_workspaces", "uq_candidate_chat_workspaces_candidate"):
        conn.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_chat_workspaces_candidate
                ON candidate_chat_workspaces (candidate_id)
                """
            )
        )
    if not index_exists(conn, "candidate_chat_workspaces", "ix_candidate_chat_workspaces_updated"):
        conn.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS ix_candidate_chat_workspaces_updated
                ON candidate_chat_workspaces (updated_at)
                """
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if not table_exists(conn, "candidate_chat_workspaces"):
        return
    conn.execute(sa.text("DROP TABLE candidate_chat_workspaces"))
