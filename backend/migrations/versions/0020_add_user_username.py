"""Add username field to users table.

Revision ID: 0020_add_user_username
Revises: 0019_fix_notification_log_unique_index
Create Date: 2025-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, column_exists, index_exists


revision = "0020_add_user_username"
down_revision = "0019_fix_notification_log_unique_index"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Add username field to users table for direct Telegram chat links."""

    if not table_exists(conn, "users"):
        return

    # Добавляем колонку username
    if not column_exists(conn, "users", "username"):
        conn.execute(sa.text("""
            ALTER TABLE users
            ADD COLUMN username VARCHAR(32)
        """))

    # Создаём индекс для быстрого поиска
    if not index_exists(conn, "users", "ix_users_username"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS ix_users_username
            ON users (username)
        """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Remove username field from users table."""

    if not table_exists(conn, "users"):
        return

    # Удаляем индекс
    if index_exists(conn, "users", "ix_users_username"):
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_username"))

    # Удаляем колонку
    if column_exists(conn, "users", "username"):
        conn.execute(sa.text("ALTER TABLE users DROP COLUMN username"))
