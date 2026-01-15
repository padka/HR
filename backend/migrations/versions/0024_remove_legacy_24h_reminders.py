"""Delete legacy 24-hour reminders from scheduler and outbox."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "0024_remove_legacy_24h_reminders"
down_revision = "0023_add_interview_notes"
branch_labels = None
depends_on = None


slot_reminder_jobs = sa.table(
    "slot_reminder_jobs",
    sa.column("id", sa.Integer),
    sa.column("kind", sa.String),
)

outbox_notifications = sa.table(
    "outbox_notifications",
    sa.column("id", sa.Integer),
    sa.column("type", sa.String),
    sa.column("payload_json", sa.JSON),
)

notification_logs = sa.table(
    "notification_logs",
    sa.column("id", sa.Integer),
    sa.column("type", sa.String),
)


LEGACY_KIND = "remind_24h"
LEGACY_LOG_TYPE = f"slot_reminder:{LEGACY_KIND}"


def upgrade(conn: Connection) -> None:
    # Drop pending scheduler jobs for the legacy reminder
    conn.execute(
        slot_reminder_jobs.delete().where(slot_reminder_jobs.c.kind == LEGACY_KIND)
    )

    # Remove queued outbox notifications that would still try to send the legacy reminder
    rows = conn.execute(
        sa.select(
            outbox_notifications.c.id,
            outbox_notifications.c.payload_json,
        ).where(outbox_notifications.c.type == "slot_reminder")
    ).fetchall()
    legacy_ids = [
        row.id
        for row in rows
        if (row.payload_json or {}).get("reminder_kind") == LEGACY_KIND
    ]
    if legacy_ids:
        conn.execute(
            outbox_notifications.delete().where(
                outbox_notifications.c.id.in_(legacy_ids)
            )
        )

    # Clean up noisy notification logs, if any
    conn.execute(notification_logs.delete().where(notification_logs.c.type == LEGACY_LOG_TYPE))


def downgrade(conn: Connection) -> None:  # pragma: no cover - irreversible cleanup
    # Data cleanup is irreversible.
    pass
