"""Prevent duplicate reservations per recruiter."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import index_exists, table_exists


revision = "0007_prevent_duplicate_slot_reservations"
down_revision = "0006_add_slots_recruiter_start_index"
branch_labels = None
depends_on = None


UNIQUE_INDEX_NAME = "uq_slots_candidate_recruiter_active"
LOCKS_TABLE = "slot_reservation_locks"
LOCKS_INDEX = "uq_slot_reservation_locks_key"


def upgrade(conn: Connection) -> None:
    """Create slot_reservation_locks table and unique index on slots."""

    # Если базовые таблицы не созданы — выходим
    if not table_exists(conn, "slots") or not table_exists(conn, "recruiters"):
        return

    # Если таблица уже есть — повторно не создаём
    if not table_exists(conn, LOCKS_TABLE):
        conn.execute(sa.text(f"""
            CREATE TABLE {LOCKS_TABLE} (
                id BIGSERIAL PRIMARY KEY,
                slot_id INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
                candidate_tg_id BIGINT NOT NULL,
                recruiter_id INTEGER NOT NULL REFERENCES recruiters(id) ON DELETE CASCADE,
                reservation_date DATE NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))

    # Создаём уникальный индекс на locks
    if not index_exists(conn, LOCKS_TABLE, LOCKS_INDEX):
        conn.execute(sa.text(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {LOCKS_INDEX}
                ON {LOCKS_TABLE} (candidate_tg_id, recruiter_id, reservation_date)
        """))

    # Создаём уникальный индекс на slots
    if not index_exists(conn, "slots", UNIQUE_INDEX_NAME):
        conn.execute(sa.text(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {UNIQUE_INDEX_NAME}
                ON slots (candidate_tg_id, recruiter_id)
             WHERE lower(status) IN ('pending', 'booked')
        """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Drop slot_reservation_locks table and unique index."""
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {LOCKS_INDEX}"))
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {UNIQUE_INDEX_NAME}"))
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {LOCKS_TABLE} CASCADE"))
