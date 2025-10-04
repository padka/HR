"""Add slot reminder jobs table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "0008_add_slot_reminder_jobs"
down_revision = "0007_prevent_duplicate_slot_reservations"
branch_labels = None
depends_on = None


TABLE_NAME = "slot_reminder_jobs"


def upgrade(conn: Connection) -> None:
    conn.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
                kind VARCHAR(32) NOT NULL,
                job_id VARCHAR(255) NOT NULL,
                scheduled_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                updated_at TIMESTAMP NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                UNIQUE(slot_id, kind),
                UNIQUE(job_id)
            )
            """
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry only
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {TABLE_NAME}"))

