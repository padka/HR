"""Ensure recruiter notification template exists."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection

revision = "0026_add_recruiter_candidate_confirmed_template"
down_revision = "0025_add_intro_day_details"
branch_labels = None
depends_on = None

TEMPLATE_KEY = "recruiter_candidate_confirmed_notice"
TEMPLATE_BODY = (
    "✅ Кандидат {candidate_name} подтвердил участие.\n"
    "📅 {dt_local}\n"
    "💬 Ответственный рекрутёр: {recruiter_name}"
)


def upgrade(conn: Connection) -> None:
    exists = conn.execute(
        text(
            """
            SELECT 1
            FROM message_templates
            WHERE key = :key AND locale = 'ru' AND channel = 'tg'
            LIMIT 1
            """
        ),
        {"key": TEMPLATE_KEY},
    ).first()
    if exists:
        return

    conn.execute(
        text(
            """
            INSERT INTO message_templates (key, locale, channel, body_md, version, is_active, updated_at)
            VALUES (:key, 'ru', 'tg', :body, 1, 1, :updated_at)
            """
        ),
        {
            "key": TEMPLATE_KEY,
            "body": TEMPLATE_BODY,
            "updated_at": datetime.now(timezone.utc),
        },
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    conn.execute(
        text(
            """
            DELETE FROM message_templates
            WHERE key = :key AND locale = 'ru' AND channel = 'tg'
            """
        ),
        {"key": TEMPLATE_KEY},
    )
