"""Refresh interview notification templates for immediate and 2h reminders."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0086_update_interview_notification_templates"
down_revision = "0085_add_interview_script_feedback_and_hh_resume"
branch_labels = None
depends_on = None


_TEMPLATES = {
    "interview_confirmed_candidate": (
        "{candidate_name} 👋\n\n"
        "Поздравляем — вы шаг ближе к команде <b>SMART SERVICE</b>!\n\n"
        "🗓 <b>{slot_day_name_local}, {slot_time_local}</b> (по-вашему времени)\n\n"
        "💬 <b>Формат:</b> видеочат | 15–20 мин\n\n"
        "⚡ Что нужно заранее:\n"
        "• стабильный интернет\n"
        "• 2–3 вопроса о вакансии\n\n"
        "🔔 Не забудьте поставить напоминание на телефон."
    ),
    "confirm_2h": (
        "Добрый день, {candidate_name}! 😊\n\n"
        "⏰ Напоминаю: сегодня в {slot_time_local} (ваше время) — видеособеседование в компании Smart⚡\n\n"
        "📌 План: кратко о компании и вакансии → ваши вопросы → ожидания и рост.\n\n"
        "Проверьте интернет + камеру.\n\n"
        "Нажмите «✅ Подтверждаю», и бот сразу пришлёт ссылку на подключение."
    ),
    "att_confirmed_link": (
        "✅ Встреча подтверждена.\n\n"
        "🔗 Ссылка для подключения: {link}\n"
        "🗓 Время: {dt}"
    ),
}


def _sync_message_templates_sequence(conn: Connection) -> None:
    if conn.dialect.name != "postgresql":
        return
    conn.execute(
        sa.text(
            """
            SELECT setval(
                pg_get_serial_sequence('message_templates', 'id'),
                COALESCE((SELECT MAX(id) FROM message_templates), 1),
                EXISTS (SELECT 1 FROM message_templates)
            )
            """
        )
    )


def _upsert_active_template(conn: Connection, key: str, body: str) -> None:
    updated = conn.execute(
        sa.text(
            """
            UPDATE message_templates
               SET body_md = :body,
                   updated_at = CURRENT_TIMESTAMP
             WHERE key = :key
               AND locale = 'ru'
               AND channel = 'tg'
               AND is_active = TRUE
            """
        ),
        {"key": key, "body": body},
    )
    if (updated.rowcount or 0) > 0:
        return

    next_version = int(
        conn.execute(
            sa.text(
                """
                SELECT COALESCE(MAX(version), 0)
                  FROM message_templates
                 WHERE key = :key
                   AND locale = 'ru'
                   AND channel = 'tg'
                """
            ),
            {"key": key},
        ).scalar()
        or 0
    ) + 1

    _sync_message_templates_sequence(conn)
    conn.execute(
        sa.text(
            """
            INSERT INTO message_templates
                (key, locale, channel, body_md, version, is_active, created_at, updated_at)
            VALUES
                (:key, 'ru', 'tg', :body, :version, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {"key": key, "body": body, "version": next_version},
    )


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "message_templates"):
        return
    for key, body in _TEMPLATES.items():
        _upsert_active_template(conn, key, body)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    # Irreversible content migration: keep current template versions.
    return None
