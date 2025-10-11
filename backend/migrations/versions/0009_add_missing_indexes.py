"""Add indexes for candidate and auto message lookups."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


revision = "0009_add_missing_indexes"
down_revision = "0008_add_slot_reminder_jobs"
branch_labels = None
depends_on = None


SLOTS_TABLE = "slots"
AUTO_MESSAGES_TABLE = "auto_messages"
SLOTS_INDEX_NAME = "ix_slots_candidate_tg_id"
AUTO_MESSAGES_INDEX_NAME = "ix_auto_messages_target_chat_id"
def _dialect_name(conn: Connection) -> str:
    dialect = getattr(conn, "dialect", None)
    return dialect.name if dialect is not None else ""


def _execute(conn: Connection, statement: str) -> None:
    conn.execute(text(statement))


def upgrade(conn: Connection) -> None:
    dialect_name = _dialect_name(conn)

    create_prefix = "CREATE INDEX IF NOT EXISTS"
    if dialect_name == "sqlite":
        _execute(
            conn,
            f"{create_prefix} {SLOTS_INDEX_NAME} ON {SLOTS_TABLE} (candidate_tg_id)",
        )
        _execute(
            conn,
            f"{create_prefix} {AUTO_MESSAGES_INDEX_NAME} ON {AUTO_MESSAGES_TABLE} (target_chat_id)",
        )
        return

    if dialect_name == "postgresql":
        create_prefix = "CREATE INDEX CONCURRENTLY IF NOT EXISTS"

    _execute(
        conn,
        f"{create_prefix} {SLOTS_INDEX_NAME} ON {SLOTS_TABLE} (candidate_tg_id)",
    )
    _execute(
        conn,
        f"{create_prefix} {AUTO_MESSAGES_INDEX_NAME} ON {AUTO_MESSAGES_TABLE} (target_chat_id)",
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry only
    dialect_name = _dialect_name(conn)

    drop_prefix = "DROP INDEX IF EXISTS"
    if dialect_name == "postgresql":
        drop_prefix = "DROP INDEX CONCURRENTLY IF EXISTS"

    _execute(conn, f"{drop_prefix} {SLOTS_INDEX_NAME}")
    _execute(conn, f"{drop_prefix} {AUTO_MESSAGES_INDEX_NAME}")

