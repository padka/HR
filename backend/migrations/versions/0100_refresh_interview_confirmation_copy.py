"""Refresh candidate interview confirmation copy for current bot templates."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.apps.bot.defaults import DEFAULT_TEMPLATES
from backend.migrations.utils import table_exists

revision = "0099a_refresh_interview_confirmation_copy"
down_revision = "0099_add_users_phone_normalized"
branch_labels = None
depends_on = None


_TEMPLATES = {
    "interview_confirmed_candidate": DEFAULT_TEMPLATES["interview_confirmed_candidate"],
    "stage1_invite": DEFAULT_TEMPLATES["stage1_invite"],
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


def _upsert_global_active_template(conn: Connection, key: str, body: str) -> None:
    updated = conn.execute(
        sa.text(
            """
            UPDATE message_templates
               SET body_md = :body,
                   updated_at = CURRENT_TIMESTAMP
             WHERE key = :key
               AND locale = 'ru'
               AND channel = 'tg'
               AND city_id IS NULL
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
                   AND city_id IS NULL
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
                (key, locale, channel, body_md, version, is_active, city_id, created_at, updated_at)
            VALUES
                (:key, 'ru', 'tg', :body, :version, TRUE, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {"key": key, "body": body, "version": next_version},
    )


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "message_templates"):
        return
    for key, body in _TEMPLATES.items():
        _upsert_global_active_template(conn, key, body)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    return None
