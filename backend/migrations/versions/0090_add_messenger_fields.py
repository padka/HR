"""Add messenger platform and VK Max user ID fields to users table.

Adds:
- messenger_platform: preferred notification platform ('telegram' | 'max')
- max_user_id: VK Max user identifier for sending messages via Max bot
- messenger_channel column on outbox_notifications for routing
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists

revision = "0090_add_messenger_fields"
down_revision = "0089_add_hh_sync_fields_and_log"
branch_labels = None
depends_on = None


def _add_messenger_fields_to_users(conn: Connection) -> None:
    """Add messenger platform columns to users table."""
    columns = [
        ("messenger_platform", "VARCHAR(20) DEFAULT 'telegram'"),
        ("max_user_id", "VARCHAR(64)"),
    ]
    for col_name, col_type in columns:
        if not column_exists(conn, "users", col_name):
            conn.execute(
                sa.text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            )

    # Index on max_user_id for lookups
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_users_max_user_id "
            "ON users(max_user_id)"
        )
    )


def _add_channel_to_outbox(conn: Connection) -> None:
    """Add messenger_channel column to outbox_notifications for routing."""
    if not column_exists(conn, "outbox_notifications", "messenger_channel"):
        conn.execute(
            sa.text(
                "ALTER TABLE outbox_notifications "
                "ADD COLUMN messenger_channel VARCHAR(20) DEFAULT 'telegram'"
            )
        )


def upgrade(conn: Connection) -> None:
    _add_messenger_fields_to_users(conn)
    _add_channel_to_outbox(conn)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name == "postgresql":
        for col in ("max_user_id", "messenger_platform"):
            if column_exists(conn, "users", col):
                conn.execute(sa.text(f"ALTER TABLE users DROP COLUMN {col}"))
        if column_exists(conn, "outbox_notifications", "messenger_channel"):
            conn.execute(
                sa.text("ALTER TABLE outbox_notifications DROP COLUMN messenger_channel")
            )
    # SQLite doesn't support DROP COLUMN in older versions; skip for dev
