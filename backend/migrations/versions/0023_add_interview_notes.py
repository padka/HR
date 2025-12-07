"""Add interview_notes table for storing interview scripts and notes."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists


revision = "0023_add_interview_notes"
down_revision = "0022_add_candidate_status"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Create interview_notes table with JSONB payload support."""

    if table_exists(conn, "interview_notes"):
        return

    conn.execute(sa.text("""
        CREATE TABLE interview_notes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            interviewer_name VARCHAR(160),
            data JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Drop interview_notes table."""
    conn.execute(sa.text("DROP TABLE IF EXISTS interview_notes CASCADE"))
