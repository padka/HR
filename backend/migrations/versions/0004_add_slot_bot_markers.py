"""Add bot dispatch markers to slots"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

revision = "0004_add_slot_bot_markers"
down_revision = "0003_add_slot_interview_outcome"
branch_labels = None
depends_on = None


def _column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade(conn: Connection) -> None:
    for column in ("test2_sent_at", "rejection_sent_at"):
        if _column_exists(conn, "slots", column):
            continue
        conn.execute(
            sa.text(
                f"ALTER TABLE slots ADD COLUMN {column} TIMESTAMP WITH TIME ZONE"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry with upgrade
    for column in ("test2_sent_at", "rejection_sent_at"):
        if not _column_exists(conn, "slots", column):
            continue
        conn.execute(sa.text(f"ALTER TABLE slots DROP COLUMN {column}"))
