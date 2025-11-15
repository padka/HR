"""Add interview_notes table for storing interview scripts and notes."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0023_add_interview_notes"
down_revision = "0022_add_candidate_status"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Create interview_notes table with JSON payload support."""
    dialect = conn.dialect.name

    if dialect == "sqlite":
        id_col = "INTEGER PRIMARY KEY AUTOINCREMENT"
        json_col = "TEXT"
        json_default = "DEFAULT ('{}')"
        ts_col = "TIMESTAMP"
    elif dialect == "postgresql":
        id_col = "SERIAL PRIMARY KEY"
        json_col = "JSONB"
        json_default = "DEFAULT '{}'::jsonb"
        ts_col = "TIMESTAMP WITH TIME ZONE"
    else:
        id_col = "SERIAL PRIMARY KEY"
        json_col = "JSON"
        json_default = "DEFAULT ('{}')"
        ts_col = "TIMESTAMP WITH TIME ZONE"

    conn.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS interview_notes (
                id {id_col},
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                interviewer_name VARCHAR(160),
                data {json_col} NOT NULL {json_default},
                created_at {ts_col} NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                updated_at {ts_col} NOT NULL DEFAULT (CURRENT_TIMESTAMP)
            )
            """
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    conn.execute(sa.text("DROP TABLE IF EXISTS interview_notes"))
