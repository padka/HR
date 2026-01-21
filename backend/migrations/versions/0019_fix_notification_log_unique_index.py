"""Fix notification_logs unique index to include candidate_tg_id."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, index_exists


revision = "0019_fix_notification_log_unique_index"
down_revision = "0018_slots_candidate_fields"
branch_labels = None
depends_on = None


TABLE_NAME = "notification_logs"
OLD_CONSTRAINT = "uq_notification_logs_type_booking"
NEW_INDEX = "uq_notif_type_booking_candidate"


def upgrade(conn: Connection) -> None:
    """Update unique index to include candidate_tg_id."""

    if not table_exists(conn, TABLE_NAME):
        return

    # Заполняем недостающие candidate_tg_id из slots
    conn.execute(sa.text(f"""
        UPDATE {TABLE_NAME} AS nl
           SET candidate_tg_id = s.candidate_tg_id
          FROM slots AS s
         WHERE s.id = nl.booking_id
           AND nl.candidate_tg_id IS NULL
           AND s.candidate_tg_id IS NOT NULL
    """))

    # Удаляем старый constraint/индекс
    conn.execute(sa.text(f"""
        ALTER TABLE {TABLE_NAME}
        DROP CONSTRAINT IF EXISTS {OLD_CONSTRAINT}
    """))
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {OLD_CONSTRAINT}"))

    # Создаём новый уникальный индекс
    if not index_exists(conn, TABLE_NAME, NEW_INDEX):
        conn.execute(sa.text(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {NEW_INDEX}
                ON {TABLE_NAME} (type, booking_id, candidate_tg_id)
        """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Restore old index without candidate_tg_id."""

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
