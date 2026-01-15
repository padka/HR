"""Ensure invite token tables have auto-increment IDs on Postgres."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, column_exists

revision = "0047_fix_invite_tokens_identity"
down_revision = "0046_add_test2_invites_and_test_result_source"
branch_labels = None
depends_on = None


def _ensure_sequence_default(conn: Connection, table: str, column: str) -> None:
    if conn.dialect.name == "sqlite":
        return
    if not table_exists(conn, table) or not column_exists(conn, table, column):
        return

    row = conn.execute(
        sa.text(
            """
            SELECT is_identity, column_default
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).fetchone()
    if row:
        is_identity, column_default = row
        if str(is_identity or "").upper() == "YES":
            return
        if column_default and "nextval" in str(column_default):
            return

    seq_name = f"{table}_{column}_seq"
    conn.execute(sa.text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}"))
    max_id = conn.execute(sa.text(f"SELECT MAX({column}) FROM {table}")).scalar()
    if max_id is None:
        conn.execute(sa.text(f"SELECT setval('{seq_name}', 1, false)"))
    else:
        conn.execute(sa.text(f"SELECT setval('{seq_name}', {int(max_id)})"))
    conn.execute(
        sa.text(
            f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT nextval('{seq_name}')"
        )
    )
    conn.execute(sa.text(f"ALTER SEQUENCE {seq_name} OWNED BY {table}.{column}"))


def upgrade(conn: Connection) -> None:
    _ensure_sequence_default(conn, "candidate_invite_tokens", "id")
    _ensure_sequence_default(conn, "test2_invites", "id")


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name == "sqlite":
        return
    for table in ("candidate_invite_tokens", "test2_invites"):
        seq_name = f"{table}_id_seq"
        if table_exists(conn, table) and column_exists(conn, table, "id"):
            conn.execute(
                sa.text(f"ALTER TABLE {table} ALTER COLUMN id DROP DEFAULT")
            )
        conn.execute(sa.text(f"DROP SEQUENCE IF EXISTS {seq_name}"))
