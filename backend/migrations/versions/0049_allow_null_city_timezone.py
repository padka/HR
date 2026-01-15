"""Allow nullable timezone for cities."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, table_exists

revision = "0049_allow_null_city_timezone"
down_revision = "0048_fix_test2_invites_timezone_columns"
branch_labels = None
depends_on = None

TABLE = "cities"
COLUMN = "tz"


def upgrade(conn: Connection) -> None:
    if conn.dialect.name == "sqlite":
        return
    if not table_exists(conn, TABLE):
        return
    if not column_exists(conn, TABLE, COLUMN):
        return
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ALTER COLUMN {COLUMN} DROP NOT NULL"))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name == "sqlite":
        return
    if not table_exists(conn, TABLE):
        return
    if not column_exists(conn, TABLE, COLUMN):
        return
    conn.execute(sa.text(f"UPDATE {TABLE} SET {COLUMN} = 'Europe/Moscow' WHERE {COLUMN} IS NULL"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ALTER COLUMN {COLUMN} SET NOT NULL"))
