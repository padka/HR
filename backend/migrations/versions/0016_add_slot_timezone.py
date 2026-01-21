"""Add timezone name to slots."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import Connection


revision = "0016_add_slot_timezone"
down_revision = "0016_add_slot_interview_feedback"
branch_labels = None
depends_on = None


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    inspector = inspect(conn)
    try:
        return any(col["name"] == column for col in inspector.get_columns(table))
    except Exception:
        return False


def upgrade(conn: Connection) -> None:
    if not _column_exists(conn, "slots", "tz_name"):
        conn.execute(
            sa.text(
                "ALTER TABLE slots ADD COLUMN tz_name VARCHAR(64) "
                "NOT NULL DEFAULT 'Europe/Moscow'"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover - legacy support
    if _column_exists(conn, "slots", "tz_name"):
        conn.execute(sa.text("ALTER TABLE slots DROP COLUMN tz_name"))
