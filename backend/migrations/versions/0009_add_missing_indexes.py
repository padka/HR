"""Add indexes for candidate and auto message lookups."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, index_exists


revision = "0009_add_missing_indexes"
down_revision = "0008_add_slot_reminder_jobs"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Add indexes for candidate_tg_id and target_chat_id lookups."""
    # Создаём индексы только если таблицы существуют
    if table_exists(conn, "slots"):
        if not index_exists(conn, "slots", "ix_slots_candidate_tg_id"):
            conn.execute(sa.text(
                "CREATE INDEX IF NOT EXISTS ix_slots_candidate_tg_id "
                "ON slots (candidate_tg_id)"
            ))

    if table_exists(conn, "auto_messages"):
        if not index_exists(conn, "auto_messages", "ix_auto_messages_target_chat_id"):
            conn.execute(sa.text(
                "CREATE INDEX IF NOT EXISTS ix_auto_messages_target_chat_id "
                "ON auto_messages (target_chat_id)"
            ))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Remove the indexes."""
    if table_exists(conn, "slots"):
        if index_exists(conn, "slots", "ix_slots_candidate_tg_id"):
            conn.execute(sa.text("DROP INDEX IF EXISTS ix_slots_candidate_tg_id"))

    if table_exists(conn, "auto_messages"):
        if index_exists(conn, "auto_messages", "ix_auto_messages_target_chat_id"):
            conn.execute(sa.text("DROP INDEX IF EXISTS ix_auto_messages_target_chat_id"))
