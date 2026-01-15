"""Update slot unique index to include purpose field.

This migration updates the unique index on slots table to prevent duplicate
bookings per candidate+recruiter+purpose combination, instead of just
candidate+recruiter. This allows the same candidate to have both an interview
slot and an intro_day slot with the same recruiter.

Revision ID: 0021_update_slot_unique_index_include_purpose
Revises: 0020_add_user_username
Create Date: 2025-11-05 16:45:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, index_exists


revision = "0021_update_slot_unique_index_include_purpose"
down_revision = "0020_add_user_username"
branch_labels = None
depends_on = None


TABLE_NAME = "slots"
OLD_INDEX_NAME = "uq_slots_candidate_recruiter_active"
NEW_INDEX_NAME = "uq_slots_candidate_recruiter_purpose_active"


def upgrade(conn: Connection) -> None:
    """Update unique index to include purpose field."""

    if not table_exists(conn, TABLE_NAME):
        return

    # Удаляем старый индекс
    if index_exists(conn, TABLE_NAME, OLD_INDEX_NAME):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {OLD_INDEX_NAME}"))

    # Создаём новый индекс с полем purpose
    if not index_exists(conn, TABLE_NAME, NEW_INDEX_NAME):
        conn.execute(sa.text(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {NEW_INDEX_NAME}
                ON {TABLE_NAME} (candidate_tg_id, recruiter_id, purpose)
             WHERE lower(status) IN ('pending','booked','confirmed_by_candidate')
        """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Restore old index without purpose field."""

    if not table_exists(conn, TABLE_NAME):
        return

    # Удаляем новый индекс
    if index_exists(conn, TABLE_NAME, NEW_INDEX_NAME):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {NEW_INDEX_NAME}"))

    # Восстанавливаем старый индекс
    if not index_exists(conn, TABLE_NAME, OLD_INDEX_NAME):
        conn.execute(sa.text(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {OLD_INDEX_NAME}
                ON {TABLE_NAME} (candidate_tg_id, recruiter_id)
             WHERE lower(status) IN ('pending','booked','confirmed_by_candidate')
        """))
