"""Enhance notification_logs with retry/status tracking fields."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, column_exists


revision = "0013_enhance_notification_logs"
down_revision = "0012_update_slots_candidate_recruiter_index"
branch_labels = None
depends_on = None


TABLE_NAME = "notification_logs"
STATUS_COLUMN = "status"
ATTEMPTS_COLUMN = "attempts"
LAST_ERROR_COLUMN = "last_error"
NEXT_RETRY_COLUMN = "next_retry_at"


def upgrade(conn: Connection) -> None:
    """Add retry and status tracking columns to notification_logs."""

    if not table_exists(conn, TABLE_NAME):
        return

    # Добавляем колонки, если их нет
    if not column_exists(conn, TABLE_NAME, STATUS_COLUMN):
        conn.execute(sa.text(f"""
            ALTER TABLE {TABLE_NAME}
            ADD COLUMN {STATUS_COLUMN} VARCHAR(20) NOT NULL DEFAULT 'sent'
        """))

    if not column_exists(conn, TABLE_NAME, ATTEMPTS_COLUMN):
        conn.execute(sa.text(f"""
            ALTER TABLE {TABLE_NAME}
            ADD COLUMN {ATTEMPTS_COLUMN} INTEGER NOT NULL DEFAULT 1
        """))

    if not column_exists(conn, TABLE_NAME, LAST_ERROR_COLUMN):
        conn.execute(sa.text(f"""
            ALTER TABLE {TABLE_NAME}
            ADD COLUMN {LAST_ERROR_COLUMN} TEXT
        """))

    if not column_exists(conn, TABLE_NAME, NEXT_RETRY_COLUMN):
        conn.execute(sa.text(f"""
            ALTER TABLE {TABLE_NAME}
            ADD COLUMN {NEXT_RETRY_COLUMN} TIMESTAMP WITH TIME ZONE
        """))

    # Убираем server defaults после создания колонок
    conn.execute(sa.text(f"ALTER TABLE {TABLE_NAME} ALTER COLUMN {STATUS_COLUMN} DROP DEFAULT"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE_NAME} ALTER COLUMN {ATTEMPTS_COLUMN} DROP DEFAULT"))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Remove retry and status tracking columns."""

    if not table_exists(conn, TABLE_NAME):
        return

    if column_exists(conn, TABLE_NAME, NEXT_RETRY_COLUMN):
        conn.execute(sa.text(f"ALTER TABLE {TABLE_NAME} DROP COLUMN {NEXT_RETRY_COLUMN}"))

    if column_exists(conn, TABLE_NAME, LAST_ERROR_COLUMN):
        conn.execute(sa.text(f"ALTER TABLE {TABLE_NAME} DROP COLUMN {LAST_ERROR_COLUMN}"))

    if column_exists(conn, TABLE_NAME, ATTEMPTS_COLUMN):
        conn.execute(sa.text(f"ALTER TABLE {TABLE_NAME} DROP COLUMN {ATTEMPTS_COLUMN}"))

    if column_exists(conn, TABLE_NAME, STATUS_COLUMN):
        conn.execute(sa.text(f"ALTER TABLE {TABLE_NAME} DROP COLUMN {STATUS_COLUMN}"))

