"""Create message_templates and outbox_notifications tables."""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, column_exists, index_exists


revision = "0014_notification_outbox_and_templates"
down_revision = "0013_enhance_notification_logs"
branch_labels = None
depends_on = None


TABLE_MESSAGE_TEMPLATES = "message_templates"
TABLE_OUTBOX = "outbox_notifications"
TABLE_NOTIFICATION_LOGS = "notification_logs"


def upgrade(conn: Connection) -> None:
    """Create message_templates and outbox_notifications tables."""

    # Создаём таблицу message_templates
    if not table_exists(conn, TABLE_MESSAGE_TEMPLATES):
        conn.execute(sa.text("""
            CREATE TABLE message_templates (
                id SERIAL PRIMARY KEY,
                key VARCHAR(100) NOT NULL,
                locale VARCHAR(16) NOT NULL DEFAULT 'ru',
                channel VARCHAR(32) NOT NULL DEFAULT 'tg',
                body_md TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_template_key_locale_channel_version
                    UNIQUE (key, locale, channel, version)
            )
        """))

    # Создаём индекс для message_templates
    if not index_exists(conn, TABLE_MESSAGE_TEMPLATES, "ix_template_active_lookup"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS ix_template_active_lookup
                ON message_templates (key, locale, channel, is_active)
        """))

    # Создаём таблицу outbox_notifications
    if not table_exists(conn, TABLE_OUTBOX):
        conn.execute(sa.text("""
            CREATE TABLE outbox_notifications (
                id SERIAL PRIMARY KEY,
                booking_id INTEGER,
                type VARCHAR(50) NOT NULL,
                payload_json JSON,
                candidate_tg_id BIGINT,
                recruiter_tg_id BIGINT,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                locked_at TIMESTAMP WITH TIME ZONE,
                next_retry_at TIMESTAMP WITH TIME ZONE,
                last_error TEXT,
                correlation_id VARCHAR(64),
                CONSTRAINT fk_outbox_booking_id
                    FOREIGN KEY (booking_id) REFERENCES slots(id) ON DELETE CASCADE
            )
        """))

    # Создаём индексы для outbox_notifications
    if not index_exists(conn, TABLE_OUTBOX, "uq_outbox_type_booking_candidate"):
        conn.execute(sa.text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_outbox_type_booking_candidate
                ON outbox_notifications (type, booking_id, candidate_tg_id)
        """))

    if not index_exists(conn, TABLE_OUTBOX, "ix_outbox_status_next_retry"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS ix_outbox_status_next_retry
                ON outbox_notifications (status, next_retry_at)
        """))

    # Добавляем колонки в notification_logs
    if table_exists(conn, TABLE_NOTIFICATION_LOGS):
        if not column_exists(conn, TABLE_NOTIFICATION_LOGS, "template_key"):
            conn.execute(sa.text(f"""
                ALTER TABLE {TABLE_NOTIFICATION_LOGS}
                ADD COLUMN template_key VARCHAR(100)
            """))

        if not column_exists(conn, TABLE_NOTIFICATION_LOGS, "template_version"):
            conn.execute(sa.text(f"""
                ALTER TABLE {TABLE_NOTIFICATION_LOGS}
                ADD COLUMN template_version INTEGER
            """))

    # Заполняем начальные шаблоны
    seed_data = [
        {
            "key": "interview_confirmed_candidate",
            "locale": "ru",
            "channel": "tg",
            "body_md": (
                "{candidate_name} 👋\n"
                "Поздравляем — вы шаг ближе к команде **SMART SERVICE**!\n\n"
                "🗓 {dt_local}\n"
                "💬 Формат: видеочат | 15–20 мин\n\n"
                "⚡ Что нужно заранее:\n"
                "• стабильный интернет\n"
                "• 2–3 вопроса о вакансии\n\n"
                "🔔 Не забудьте поставить напоминание на телефон."
            ),
            "version": 1,
        },
        {
            "key": "interview_reminder_2h",
            "locale": "ru",
            "channel": "tg",
            "body_md": (
                "Напоминаем: интервью начнётся через 2 часа.\n\n"
                "🗓 {dt_local}\n"
                "🔗 Ссылка на встречу: {join_link}\n\n"
                "Если планы поменялись — напишите нам, чтобы подобрать другое время."
            ),
            "version": 1,
        },
        {
            "key": "recruiter_candidate_confirmed_notice",
            "locale": "ru",
            "channel": "tg",
            "body_md": (
                "✅ Кандидат {candidate_name} подтвердил участие\n"
                "📅 {dt_local}\n"
                "💬 Рекрутёр: {recruiter_name}"
            ),
            "version": 1,
        },
        {
            "key": "candidate_reschedule_prompt",
            "locale": "ru",
            "channel": "tg",
            "body_md": (
                "🔁 Мы освободили ваш слот.\n"
                "Выберите, пожалуйста, новое время в расписании — просто нажмите кнопку «Выбрать слот»."
            ),
            "version": 1,
        },
        {
            "key": "no_slots_fallback",
            "locale": "ru",
            "channel": "tg",
            "body_md": (
                "Свободных слотов сейчас нет.\n"
                "Оставьте сообщение рекрутёру — мы подберём интервью и вернёмся с предложением времени."
            ),
            "version": 1,
        },
    ]

    for template in seed_data:
        # Проверяем, не существует ли уже такой шаблон
        result = conn.execute(
            sa.text(
                "SELECT 1 FROM message_templates "
                "WHERE key = :key AND locale = :locale AND channel = :channel AND version = :version"
            ),
            {
                "key": template["key"],
                "locale": template["locale"],
                "channel": template["channel"],
                "version": template["version"],
            },
        ).fetchone()

        if not result:
            now = datetime.now(timezone.utc)
            conn.execute(
                sa.text("""
                    INSERT INTO message_templates (
                        key, locale, channel, body_md, version, is_active, created_at, updated_at
                    )
                    VALUES (:key, :locale, :channel, :body_md, :version, true, :created_at, :updated_at)
                """),
                {
                    "key": template["key"],
                    "locale": template["locale"],
                    "channel": template["channel"],
                    "body_md": template["body_md"],
                    "version": template["version"],
                    "created_at": now,
                    "updated_at": now,
                },
            )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Drop message_templates and outbox_notifications tables."""

    if table_exists(conn, TABLE_NOTIFICATION_LOGS):
        if column_exists(conn, TABLE_NOTIFICATION_LOGS, "template_version"):
            conn.execute(sa.text(f"ALTER TABLE {TABLE_NOTIFICATION_LOGS} DROP COLUMN template_version"))

        if column_exists(conn, TABLE_NOTIFICATION_LOGS, "template_key"):
            conn.execute(sa.text(f"ALTER TABLE {TABLE_NOTIFICATION_LOGS} DROP COLUMN template_key"))

    conn.execute(sa.text(f"DROP TABLE IF EXISTS {TABLE_OUTBOX} CASCADE"))
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {TABLE_MESSAGE_TEMPLATES} CASCADE"))
