"""Add responsible recruiter reference for candidates."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, column_exists

revision = "0045_add_candidate_responsible_recruiter"
down_revision = "0044_add_lead_statuses_to_candidate_enum"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "users"):
        return
    if not column_exists(conn, "users", "responsible_recruiter_id"):
        conn.execute(
            sa.text(
                "ALTER TABLE users ADD COLUMN responsible_recruiter_id INTEGER"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name == "sqlite":
        return
    if column_exists(conn, "users", "responsible_recruiter_id"):
        conn.execute(sa.text("ALTER TABLE users DROP COLUMN responsible_recruiter_id"))
