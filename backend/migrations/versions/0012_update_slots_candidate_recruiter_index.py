"""Update slots unique index to include confirmed_by_candidate status."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, index_exists


revision = "0012_update_slots_candidate_recruiter_index"
down_revision = "0011_add_candidate_binding_to_notification_logs"
branch_labels = None
depends_on = None


TABLE_NAME = "slots"
INDEX_NAME = "uq_slots_candidate_recruiter_active"


def upgrade(conn: Connection) -> None:
    """Recreate unique index with confirmed_by_candidate status included."""

    if not table_exists(conn, TABLE_NAME):
        return

    # Удаляем старый индекс
    if index_exists(conn, TABLE_NAME, INDEX_NAME):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))

    # Создаём новый индекс с обновлённым WHERE условием
    conn.execute(sa.text(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
            ON {TABLE_NAME} (candidate_tg_id, recruiter_id)
         WHERE lower(status) IN ('pending','booked','confirmed_by_candidate')
    """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Restore old index without confirmed_by_candidate status."""

    if not table_exists(conn, TABLE_NAME):
        return

    # Удаляем новый индекс
    if index_exists(conn, TABLE_NAME, INDEX_NAME):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))

    # Создаём старый индекс
    conn.execute(sa.text(f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
            ON {TABLE_NAME} (candidate_tg_id, recruiter_id)
         WHERE lower(status) IN ('pending','booked')
    """))
