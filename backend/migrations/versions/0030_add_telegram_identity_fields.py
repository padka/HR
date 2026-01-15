"""Store Telegram identity metadata for candidates."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0030_add_telegram_identity_fields"
down_revision = "0029_add_manual_slot_availability"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    dialect = conn.dialect.name
    ts_col = "TIMESTAMP WITH TIME ZONE"
    if dialect == "sqlite":
        ts_col = "TIMESTAMP"

    conn.execute(sa.text("ALTER TABLE users ADD COLUMN telegram_user_id BIGINT"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN telegram_username TEXT"))
    conn.execute(sa.text(f"ALTER TABLE users ADD COLUMN telegram_linked_at {ts_col}"))

    conn.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_telegram_user_id "
            "ON users (telegram_user_id)"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE users SET telegram_user_id = telegram_id "
            "WHERE telegram_user_id IS NULL"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE users SET telegram_username = username "
            "WHERE telegram_username IS NULL AND username IS NOT NULL"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE users SET telegram_linked_at = COALESCE(telegram_linked_at, CURRENT_TIMESTAMP) "
            "WHERE telegram_user_id IS NOT NULL"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    if conn.dialect.name == "sqlite":
        return

    conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_telegram_user_id"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN telegram_linked_at"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN telegram_username"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN telegram_user_id"))
