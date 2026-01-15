
"""Add analytics_events table and use_jinja flag to message_templates.

Revision ID: 0035_add_analytics_events_and_jinja_flag
Revises: 0034_message_templates_city_support
Create Date: 2025-12-01 15:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, column_exists, index_exists


revision = "0035_add_analytics_events_and_jinja_flag"
down_revision = "0034_message_templates_city_support"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Apply migration: add analytics_events table and use_jinja flag."""

    # Создаём таблицу analytics_events
    if not table_exists(conn, "analytics_events"):
        conn.execute(sa.text("""
            CREATE TABLE analytics_events (
                id SERIAL PRIMARY KEY,
                event_name VARCHAR(100) NOT NULL,
                user_id BIGINT,
                candidate_id INTEGER,
                city_id INTEGER,
                slot_id INTEGER,
                booking_id INTEGER,
                metadata TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))

    # Создаём индексы для эффективного поиска
    if not index_exists(conn, "analytics_events", "idx_analytics_events_event_name"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS idx_analytics_events_event_name
                ON analytics_events (event_name)
        """))

    if not index_exists(conn, "analytics_events", "idx_analytics_events_candidate_id"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS idx_analytics_events_candidate_id
                ON analytics_events (candidate_id)
        """))

    if not index_exists(conn, "analytics_events", "idx_analytics_events_created_at"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at
                ON analytics_events (created_at)
        """))

    if not index_exists(conn, "analytics_events", "idx_analytics_events_user_id"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS idx_analytics_events_user_id
                ON analytics_events (user_id)
        """))

    # Добавляем флаг use_jinja в message_templates
    if table_exists(conn, "message_templates") and not column_exists(conn, "message_templates", "use_jinja"):
        conn.execute(sa.text("""
            ALTER TABLE message_templates
            ADD COLUMN use_jinja BOOLEAN NOT NULL DEFAULT false
        """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Revert migration: drop analytics_events table and use_jinja flag."""

    # Удаляем индексы
    if index_exists(conn, "analytics_events", "idx_analytics_events_user_id"):
        conn.execute(sa.text("DROP INDEX IF EXISTS idx_analytics_events_user_id"))

    if index_exists(conn, "analytics_events", "idx_analytics_events_created_at"):
        conn.execute(sa.text("DROP INDEX IF EXISTS idx_analytics_events_created_at"))

    if index_exists(conn, "analytics_events", "idx_analytics_events_candidate_id"):
        conn.execute(sa.text("DROP INDEX IF EXISTS idx_analytics_events_candidate_id"))

    if index_exists(conn, "analytics_events", "idx_analytics_events_event_name"):
        conn.execute(sa.text("DROP INDEX IF EXISTS idx_analytics_events_event_name"))

    # Удаляем таблицу
    conn.execute(sa.text("DROP TABLE IF EXISTS analytics_events CASCADE"))

    # Удаляем колонку use_jinja
    if table_exists(conn, "message_templates") and column_exists(conn, "message_templates", "use_jinja"):
        conn.execute(sa.text("ALTER TABLE message_templates DROP COLUMN use_jinja"))
