"""Add rejection_reason to users table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists

revision = "0063_add_candidate_rejection_reason"
down_revision = "0062_slot_assignments"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if not column_exists(conn, "users", "rejection_reason"):
        conn.execute(
            sa.text(
                "ALTER TABLE users ADD COLUMN rejection_reason TEXT"
            )
        )


def downgrade(conn: Connection) -> None:
    if column_exists(conn, "users", "rejection_reason"):
        if conn.dialect.name != "sqlite":
            conn.execute(sa.text("ALTER TABLE users DROP COLUMN rejection_reason"))
