"""Add interview feedback column to slots"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import Connection


revision = "0016_add_slot_interview_feedback"
down_revision = "0015_add_kpi_weekly_table"
branch_labels = None
depends_on = None


def _column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade(conn: Connection) -> None:
    if _column_exists(conn, "slots", "interview_feedback"):
        return
    conn.execute(sa.text("ALTER TABLE slots ADD COLUMN interview_feedback JSON"))


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry with upgrade
    if not _column_exists(conn, "slots", "interview_feedback"):
        return
    conn.execute(sa.text("ALTER TABLE slots DROP COLUMN interview_feedback"))

