"""Restore city responsible recruiter column for ownership logic."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, table_exists


revision = "0054_restore_city_responsible_recruiter"
down_revision = "0053_add_outbox_notification_indexes"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "cities"):
        return

    if not column_exists(conn, "cities", "responsible_recruiter_id"):
        conn.execute(
            sa.text(
                """
                ALTER TABLE cities
                ADD COLUMN responsible_recruiter_id INTEGER
                    REFERENCES recruiters(id) ON DELETE SET NULL
                """
            )
        )

    # Backfill from recruiter_cities if present and one-to-one
    if table_exists(conn, "recruiter_cities"):
        conn.execute(
            sa.text(
                """
                UPDATE cities AS c
                SET responsible_recruiter_id = rc.recruiter_id
                FROM recruiter_cities rc
                WHERE c.id = rc.city_id
                  AND c.responsible_recruiter_id IS NULL
                """
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if table_exists(conn, "cities") and column_exists(conn, "cities", "responsible_recruiter_id"):
        conn.execute(sa.text("ALTER TABLE cities DROP COLUMN responsible_recruiter_id"))
