"""Add conversation mode fields for candidates."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

revision = "0032_add_conversation_mode"
down_revision = "0031_add_chat_messages"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    dialect = conn.dialect.name
    ts_col = "TIMESTAMP WITH TIME ZONE"
    if dialect == "sqlite":
        ts_col = "TIMESTAMP"

    conn.execute(
        text(
            "ALTER TABLE users ADD COLUMN conversation_mode VARCHAR(16) "
            "NOT NULL DEFAULT 'flow'"
        )
    )
    conn.execute(
        text(
            f"ALTER TABLE users ADD COLUMN conversation_mode_expires_at {ts_col}"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    if conn.dialect.name == "sqlite":
        return
    conn.execute(text("ALTER TABLE users DROP COLUMN conversation_mode_expires_at"))
    conn.execute(text("ALTER TABLE users DROP COLUMN conversation_mode"))
