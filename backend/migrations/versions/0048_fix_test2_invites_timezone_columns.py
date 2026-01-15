"""Ensure Test2 invite timestamps use timezone-aware columns."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, table_exists

revision = "0048_fix_test2_invites_timezone_columns"
down_revision = "0047_fix_invite_tokens_identity"
branch_labels = None
depends_on = None


TABLE = "test2_invites"
TZ_COLUMNS = ("created_at", "expires_at", "opened_at", "completed_at")


def _is_timestamptz(conn: Connection, table: str, column: str) -> bool:
    row = conn.execute(
        sa.text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).fetchone()
    return bool(row and row[0] == "timestamp with time zone")


def upgrade(conn: Connection) -> None:
    if conn.dialect.name == "sqlite":
        return
    if not table_exists(conn, TABLE):
        return
    for column in TZ_COLUMNS:
        if not column_exists(conn, TABLE, column):
            continue
        if _is_timestamptz(conn, TABLE, column):
            continue
        conn.execute(
            sa.text(
                f"ALTER TABLE {TABLE} ALTER COLUMN {column} "
                f"TYPE TIMESTAMPTZ USING {column} AT TIME ZONE 'UTC'"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name == "sqlite":
        return
    if not table_exists(conn, TABLE):
        return
    for column in TZ_COLUMNS:
        if not column_exists(conn, TABLE, column):
            continue
        conn.execute(
            sa.text(
                f"ALTER TABLE {TABLE} ALTER COLUMN {column} "
                f"TYPE TIMESTAMP WITHOUT TIME ZONE USING {column} AT TIME ZONE 'UTC'"
            )
        )
