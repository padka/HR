"""Add chat messages table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.engine import Connection

revision = "0031_add_chat_messages"
down_revision = "0030_add_telegram_identity_fields"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    metadata = MetaData()
    users = Table("users", metadata, autoload_with=conn)
    chat_messages = Table(
        "chat_messages",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column(
            "candidate_id",
            Integer,
            ForeignKey(users.c.id, ondelete="CASCADE"),
            nullable=False,
        ),
        Column("direction", String(16), nullable=False),
        Column("channel", String(32), nullable=False, server_default="telegram"),
        Column("telegram_user_id", BigInteger, nullable=True),
        Column("telegram_message_id", BigInteger, nullable=True),
        Column("text", Text, nullable=True),
        Column("payload_json", JSON, nullable=True),
        Column("status", String(16), nullable=False),
        Column("error", Text, nullable=True),
        Column("author_label", String(160), nullable=True),
        Column("client_request_id", String(64), nullable=True, unique=True),
        Column(
            "created_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    chat_messages.create(conn, checkfirst=True)
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_candidate_created_at "
            "ON chat_messages (candidate_id, created_at DESC)"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    metadata = MetaData()
    chat_messages = Table("chat_messages", metadata)
    chat_messages.drop(conn, checkfirst=True)
