"""Add soft-delete flag to detailization entries."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists, table_exists

revision = "0081_add_detailization_soft_delete"
down_revision = "0080_slot_overlap_per_purpose"
branch_labels = None
depends_on = None

TABLE = "detailization_entries"
COL = "is_deleted"
IDX = "ix_detailization_entries_is_deleted"


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, TABLE):
        return

    if not column_exists(conn, TABLE, COL):
        conn.execute(
            sa.text(
                f"ALTER TABLE {TABLE} ADD COLUMN {COL} BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )

    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(f"UPDATE {TABLE} SET {COL}=FALSE WHERE {COL} IS NULL"))

    if not index_exists(conn, TABLE, IDX):
        conn.execute(sa.text(f"CREATE INDEX IF NOT EXISTS {IDX} ON {TABLE} ({COL})"))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if not table_exists(conn, TABLE):
        return

    conn.execute(sa.text(f"DROP INDEX IF EXISTS {IDX}"))
    if column_exists(conn, TABLE, COL):
        conn.execute(sa.text(f"ALTER TABLE {TABLE} DROP COLUMN {COL}"))
