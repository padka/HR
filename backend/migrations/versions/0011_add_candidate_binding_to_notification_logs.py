"""Add candidate_tg_id to notification_logs and update unique constraint."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, index_exists, column_exists


revision = "0011_add_candidate_binding_to_notification_logs"
down_revision = "0010_add_notification_logs"
branch_labels = None
depends_on = None


TABLE_NAME = "notification_logs"
CANDIDATE_COLUMN = "candidate_tg_id"
OLD_CONSTRAINT = "uq_notification_logs_type_booking"
NEW_INDEX = "uq_notif_type_booking_candidate"


def upgrade(conn: Connection) -> None:
    """Add candidate_tg_id column and update unique constraint."""

    if not table_exists(conn, TABLE_NAME):
        return

    # Добавляем колонку candidate_tg_id
    if not column_exists(conn, TABLE_NAME, CANDIDATE_COLUMN):
        conn.execute(sa.text(f"""
            ALTER TABLE {TABLE_NAME}
            ADD COLUMN {CANDIDATE_COLUMN} BIGINT
        """))

    # Удаляем старый constraint
    conn.execute(sa.text(f"""
        ALTER TABLE {TABLE_NAME}
        DROP CONSTRAINT IF EXISTS {OLD_CONSTRAINT}
    """))

    # Заполняем candidate_tg_id из связанных слотов
    conn.execute(sa.text(f"""
        UPDATE {TABLE_NAME} nl
           SET {CANDIDATE_COLUMN} = s.candidate_tg_id
          FROM slots s
         WHERE nl.booking_id = s.id
           AND nl.{CANDIDATE_COLUMN} IS NULL
           AND s.candidate_tg_id IS NOT NULL
    """))

    # Создаём новый уникальный индекс
    if not index_exists(conn, TABLE_NAME, NEW_INDEX):
        conn.execute(sa.text(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {NEW_INDEX}
                ON {TABLE_NAME} (type, booking_id, {CANDIDATE_COLUMN})
        """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Remove candidate_tg_id column and restore old constraint."""

    if not table_exists(conn, TABLE_NAME):
        return

    # Удаляем новый индекс
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {NEW_INDEX}"))

    # Восстанавливаем старый constraint
    conn.execute(sa.text(f"""
        ALTER TABLE {TABLE_NAME}
        ADD CONSTRAINT {OLD_CONSTRAINT}
            UNIQUE (type, booking_id)
    """))

    # Удаляем колонку
    if column_exists(conn, TABLE_NAME, CANDIDATE_COLUMN):
        conn.execute(sa.text(f"""
            ALTER TABLE {TABLE_NAME}
            DROP COLUMN {CANDIDATE_COLUMN}
        """))
