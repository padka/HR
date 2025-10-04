"""Add profile fields to cities."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import Connection


revision = "0005_add_city_profile_fields"
down_revision = "0004_add_slot_bot_markers"
branch_labels = None
depends_on = None


def _column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    inspector = inspect(conn)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade(conn: Connection) -> None:
    additions = (
        ("criteria", "TEXT"),
        ("experts", "TEXT"),
        ("plan_week", "INTEGER"),
        ("plan_month", "INTEGER"),
    )
    for column, column_type in additions:
        if _column_exists(conn, "cities", column):
            continue
        conn.execute(sa.text(f"ALTER TABLE cities ADD COLUMN {column} {column_type}"))


def downgrade(conn: Connection) -> None:  # pragma: no cover - provided for symmetry
    for column in ("criteria", "experts", "plan_week", "plan_month"):
        if not _column_exists(conn, "cities", column):
            continue
        conn.execute(sa.text(f"ALTER TABLE cities DROP COLUMN {column}"))

