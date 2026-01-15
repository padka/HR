"""Introduce notification and callback logs, extend slot status column."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists


revision = "0010_add_notification_logs"
down_revision = "0009_add_missing_indexes"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Add notification_logs and telegram_callback_logs tables, expand slots.status."""

    # Расширяем колонку status в таблице slots
    if table_exists(conn, "slots"):
        conn.execute(sa.text(
            "ALTER TABLE slots ALTER COLUMN status TYPE VARCHAR(32)"
        ))

    # Создаём таблицу notification_logs
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS notification_logs (
            id SERIAL PRIMARY KEY,
            booking_id INTEGER NOT NULL,
            type VARCHAR(50) NOT NULL,
            payload TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            CONSTRAINT fk_notification_logs_booking_id
                FOREIGN KEY (booking_id) REFERENCES slots(id) ON DELETE CASCADE,
            CONSTRAINT uq_notification_logs_type_booking
                UNIQUE (type, booking_id)
        )
    """))

    # Создаём таблицу telegram_callback_logs
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS telegram_callback_logs (
            id SERIAL PRIMARY KEY,
            callback_id VARCHAR(128) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            CONSTRAINT uq_telegram_callback_logs_callback_id
                UNIQUE (callback_id)
        )
    """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Remove notification_logs and telegram_callback_logs tables."""
    conn.execute(sa.text("DROP TABLE IF EXISTS telegram_callback_logs CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS notification_logs CASCADE"))

    if table_exists(conn, "slots"):
        conn.execute(sa.text(
            "ALTER TABLE slots ALTER COLUMN status TYPE VARCHAR(20)"
        ))

