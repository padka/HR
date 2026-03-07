"""Upgrade candidate-facing Telegram templates with full production copy."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.apps.bot.defaults import DEFAULT_TEMPLATES
from backend.migrations.utils import table_exists

revision = "0088_upgrade_candidate_template_texts"
down_revision = "0087_update_t1_done_template"
branch_labels = None
depends_on = None


_CANDIDATE_TEMPLATE_KEYS = (
    "choose_recruiter",
    "slot_taken",
    "slot_sent",
    "slot_reschedule",
    "manual_schedule_prompt",
    "approved_msg",
    "interview_confirmed_candidate",
    "interview_confirmed",
    "interview_invite_details",
    "interview_preparation",
    "existing_reservation",
    "reminder_6h",
    "reminder_3h",
    "reminder_2h",
    "reminder_30m",
    "confirm_6h",
    "confirm_3h",
    "confirm_2h",
    "interview_remind_confirm_2h",
    "att_confirmed_link",
    "att_declined",
    "att_confirmed_ack",
    "result_fail",
    "candidate_rejection",
    "intro_day_invitation",
    "intro_day_invite_city",
    "intro_day_invite",
    "intro_day_reminder",
    "intro_day_remind_2h",
    "t1_intro",
    "t1_progress",
    "t1_done",
    "t1_format_reject",
    "t1_format_clarify",
    "t1_schedule_reject",
    "t2_intro",
    "t2_result",
    "no_slots",
    "slot_proposal",
    "slot_proposal_candidate",
    "reschedule_prompt",
    "candidate_reschedule_prompt",
    "reschedule_approved_candidate",
    "reschedule_declined_candidate",
    "slot_assignment_offer",
    "slot_assignment_reschedule_approved",
    "slot_assignment_reschedule_declined",
    "slot_assignment_reschedule_requested",
    "stage1_invite",
    "stage2_interview_reminder",
    "stage3_intro_invite",
    "stage4_intro_reminder",
    "no_show_gentle",
)

_TEMPLATES = {key: DEFAULT_TEMPLATES[key] for key in _CANDIDATE_TEMPLATE_KEYS if key in DEFAULT_TEMPLATES}


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
                   AND city_id IS NULL
                """
            ),
            {"key": key},
        ).scalar()
        or 0
    ) + 1

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
        _upsert_active_template(conn, key, body)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    # Irreversible content migration: keep current template versions.
    return None
