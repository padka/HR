"""Add recovery metadata for outbound MAX chat message delivery.

This migration is additive and safe to deploy before runtime wiring is enabled.
It prepares chat_messages for async recovery of stuck outbound MAX messages.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists, table_exists

revision = "0106_chat_message_delivery_recovery_fields"
down_revision = "0105_unique_users_max_user_id"
branch_labels = None
depends_on = None


def _add_column_if_missing(conn: Connection, table: str, column_sql: str, column_name: str) -> None:
    if table_exists(conn, table) and not column_exists(conn, table, column_name):
        conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column_sql}"))


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "chat_messages"):
        return

    _add_column_if_missing(
        conn,
        "chat_messages",
        "delivery_attempts INTEGER NOT NULL DEFAULT 0",
        "delivery_attempts",
    )
    _add_column_if_missing(
        conn,
        "chat_messages",
        "delivery_locked_at TIMESTAMP",
        "delivery_locked_at",
    )
    _add_column_if_missing(
        conn,
        "chat_messages",
        "delivery_next_retry_at TIMESTAMP",
        "delivery_next_retry_at",
    )
    _add_column_if_missing(
        conn,
        "chat_messages",
        "delivery_last_attempt_at TIMESTAMP",
        "delivery_last_attempt_at",
    )
    _add_column_if_missing(
        conn,
        "chat_messages",
        "delivery_dead_at TIMESTAMP",
        "delivery_dead_at",
    )

    if not index_exists(conn, "chat_messages", "ix_chat_messages_max_delivery_recovery"):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_chat_messages_max_delivery_recovery "
                "ON chat_messages (channel, direction, status, delivery_next_retry_at, delivery_locked_at)"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name != "postgresql" or not table_exists(conn, "chat_messages"):
        return

    if index_exists(conn, "chat_messages", "ix_chat_messages_max_delivery_recovery"):
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_chat_messages_max_delivery_recovery"))

    for column in (
        "delivery_dead_at",
        "delivery_last_attempt_at",
        "delivery_next_retry_at",
        "delivery_locked_at",
        "delivery_attempts",
    ):
        if column_exists(conn, "chat_messages", column):
            conn.execute(sa.text(f"ALTER TABLE chat_messages DROP COLUMN {column}"))
