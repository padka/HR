"""Add slot reminder jobs table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists


revision = "0008_add_slot_reminder_jobs"
down_revision = "0007_prevent_duplicate_slot_reservations"
branch_labels = None
depends_on = None


TABLE_NAME = "slot_reminder_jobs"


def upgrade(conn: Connection) -> None:
    """Create slot_reminder_jobs table for tracking scheduled reminders."""

    # Если базовая таблица слотов ещё не создана — выходим
    if not table_exists(conn, "slots"):
        return

    # Если таблица уже есть — считаем миграцию применённой
    if table_exists(conn, TABLE_NAME):
        return

    conn.execute(sa.text(f"""
        CREATE TABLE {TABLE_NAME} (
            id BIGSERIAL PRIMARY KEY,
            slot_id INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
            kind VARCHAR(32) NOT NULL,
            job_id VARCHAR(255) NOT NULL,
            scheduled_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(slot_id, kind),
            UNIQUE(job_id)
        )
    """))
    conn.commit()


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Drop slot_reminder_jobs table."""
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {TABLE_NAME} CASCADE"))
    conn.commit()
