"""Add interview outcome to slots"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

revision = "0003_add_slot_interview_outcome"
down_revision = "0002_seed_defaults"
branch_labels = None
depends_on = None


def _column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade(conn: Connection) -> None:
    if _column_exists(conn, "slots", "interview_outcome"):
        return
    conn.execute(sa.text("ALTER TABLE slots ADD COLUMN interview_outcome VARCHAR(20)"))


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry with upgrade
    if not _column_exists(conn, "slots", "interview_outcome"):
        return
    conn.execute(sa.text("ALTER TABLE slots DROP COLUMN interview_outcome"))
