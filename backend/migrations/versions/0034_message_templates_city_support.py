"""Add city support to message_templates and create history table."""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, index_exists, column_exists


revision = "0034_message_templates_city_support"
down_revision = "0033_add_intro_decline_reason"
branch_labels = None
depends_on = None


TABLE_OLD = "message_templates"
TABLE_NEW = "message_templates_v2"
TABLE_HISTORY = "message_template_history"


def upgrade(conn: Connection) -> None:
    """Add city_id support and history tracking to message_templates."""

    if not table_exists(conn, TABLE_OLD):
        return

    # Проверяем, была ли уже применена миграция (есть ли city_id колонка)
    if column_exists(conn, TABLE_OLD, "city_id"):
        # Миграция уже применена, просто убедимся что history таблица создана
        if not table_exists(conn, TABLE_HISTORY):
            conn.execute(sa.text(f"""
                CREATE TABLE {TABLE_HISTORY} (
                    id SERIAL PRIMARY KEY,
                    template_id INTEGER NOT NULL,
                    key VARCHAR(100) NOT NULL,
                    locale VARCHAR(16) NOT NULL,
                    channel VARCHAR(32) NOT NULL,
                    city_id INTEGER,
                    body_md TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    updated_by VARCHAR(100),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_message_template_history_template_id
                        FOREIGN KEY (template_id) REFERENCES {TABLE_OLD}(id) ON DELETE CASCADE,
                    CONSTRAINT fk_message_template_history_city_id
                        FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE SET NULL
                )
            """))
        return

    # Создаём новую таблицу с поддержкой city_id (только если её ещё нет)
    if not table_exists(conn, TABLE_NEW):
        conn.execute(sa.text(f"""
            CREATE TABLE {TABLE_NEW} (
            id SERIAL PRIMARY KEY,
            key VARCHAR(100) NOT NULL,
            locale VARCHAR(16) NOT NULL DEFAULT 'ru',
            channel VARCHAR(32) NOT NULL DEFAULT 'tg',
            city_id INTEGER,
            body_md TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT true,
            updated_by VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_message_templates_v2_city_id
                FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE SET NULL,
            CONSTRAINT uq_template_v2_key_locale_channel_version
                UNIQUE (key, locale, channel, city_id, version)
        )
        """))

        # Копируем данные из старой таблицы
        conn.execute(sa.text(f"""
            INSERT INTO {TABLE_NEW} (id, key, locale, channel, city_id, body_md, version, is_active, updated_by, created_at, updated_at)
            SELECT id, key, locale, channel, NULL, body_md, version, is_active, NULL,
                   COALESCE(updated_at, CURRENT_TIMESTAMP),
                   COALESCE(updated_at, CURRENT_TIMESTAMP)
            FROM {TABLE_OLD}
        """))

        # Удаляем старую таблицу и переименовываем новую
        conn.execute(sa.text(f"DROP TABLE {TABLE_OLD} CASCADE"))
        conn.execute(sa.text(f"ALTER TABLE {TABLE_NEW} RENAME TO {TABLE_OLD}"))

    # Создаём индексы для быстрого поиска
    if not index_exists(conn, TABLE_OLD, "ix_template_active_lookup"):
        conn.execute(sa.text(f"""
            CREATE INDEX IF NOT EXISTS ix_template_active_lookup
                ON {TABLE_OLD} (key, locale, channel, city_id, is_active)
        """))

    if not index_exists(conn, TABLE_OLD, "ix_template_city_lookup"):
        conn.execute(sa.text(f"""
            CREATE INDEX IF NOT EXISTS ix_template_city_lookup
                ON {TABLE_OLD} (city_id, key, is_active)
        """))

    # Создаём таблицу истории
    if not table_exists(conn, TABLE_HISTORY):
        conn.execute(sa.text(f"""
            CREATE TABLE {TABLE_HISTORY} (
                id SERIAL PRIMARY KEY,
                template_id INTEGER NOT NULL,
                key VARCHAR(100) NOT NULL,
                locale VARCHAR(16) NOT NULL,
                channel VARCHAR(32) NOT NULL,
                city_id INTEGER,
                body_md TEXT NOT NULL,
                version INTEGER NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT true,
                updated_by VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_message_template_history_template_id
                    FOREIGN KEY (template_id) REFERENCES {TABLE_OLD}(id) ON DELETE CASCADE,
                CONSTRAINT fk_message_template_history_city_id
                    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE SET NULL
            )
        """))

    # Заполняем историю начальными записями
    now = datetime.now(timezone.utc)
    conn.execute(
        sa.text(f"""
            INSERT INTO {TABLE_HISTORY} (
                template_id, key, locale, channel, city_id, body_md, version, is_active, updated_by, created_at, updated_at
            )
            SELECT id, key, locale, channel, city_id, body_md, version, is_active, updated_by,
                   COALESCE(created_at, :now), COALESCE(updated_at, :now)
            FROM {TABLE_OLD}
        """),
        {"now": now},
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Drop history table (data migration not reversible)."""
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {TABLE_HISTORY} CASCADE"))
