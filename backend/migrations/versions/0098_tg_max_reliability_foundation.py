"""Add Telegram/MAX reliability fields for invites, portal sessions, and delivery telemetry."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists, table_exists

revision = "0098_tg_max_reliability_foundation"
down_revision = "0097_add_candidate_journey_archive_foundation"
branch_labels = None
depends_on = None


def _add_column_if_missing(conn: Connection, table: str, column_sql: str, column_name: str) -> None:
    if table_exists(conn, table) and not column_exists(conn, table, column_name):
        conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column_sql}"))


def _upgrade_candidate_invites(conn: Connection) -> None:
    if not table_exists(conn, "candidate_invite_tokens"):
        return

    _add_column_if_missing(
        conn,
        "candidate_invite_tokens",
        "status VARCHAR(20) NOT NULL DEFAULT 'active'",
        "status",
    )
    _add_column_if_missing(
        conn,
        "candidate_invite_tokens",
        "channel VARCHAR(20) NOT NULL DEFAULT 'generic'",
        "channel",
    )
    _add_column_if_missing(conn, "candidate_invite_tokens", "superseded_at TIMESTAMP", "superseded_at")
    _add_column_if_missing(
        conn,
        "candidate_invite_tokens",
        "used_by_external_id VARCHAR(64)",
        "used_by_external_id",
    )

    if not index_exists(
        conn,
        "candidate_invite_tokens",
        "ix_candidate_invite_tokens_candidate_channel_status",
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_candidate_invite_tokens_candidate_channel_status "
                "ON candidate_invite_tokens (candidate_id, channel, status)"
            )
        )

    conn.execute(
        sa.text(
            """
            UPDATE candidate_invite_tokens
            SET channel = COALESCE(NULLIF(TRIM(channel), ''), 'generic')
            """
        )
    )
    conn.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY candidate_id
                        ORDER BY created_at DESC, id DESC
                    ) AS row_no
                FROM candidate_invite_tokens
                WHERE channel = 'max' AND status = 'active'
            )
            UPDATE candidate_invite_tokens
            SET
                status = 'superseded',
                superseded_at = COALESCE(superseded_at, created_at)
            WHERE id IN (
                SELECT id
                FROM ranked
                WHERE row_no > 1
            )
            """
        )
    )
    if not index_exists(
        conn,
        "candidate_invite_tokens",
        "uq_candidate_invite_tokens_active_max_candidate",
    ):
        conn.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_invite_tokens_active_max_candidate "
                "ON candidate_invite_tokens (candidate_id) "
                "WHERE status = 'active' AND channel = 'max'"
            )
        )
    conn.execute(
        sa.text(
            """
            UPDATE candidate_invite_tokens
            SET
                status = CASE
                    WHEN used_at IS NOT NULL THEN 'used'
                    ELSE COALESCE(NULLIF(TRIM(status), ''), 'active')
                END,
                used_by_external_id = COALESCE(
                    NULLIF(TRIM(used_by_external_id), ''),
                    CASE
                        WHEN used_by_telegram_id IS NOT NULL THEN CAST(used_by_telegram_id AS VARCHAR(64))
                        ELSE used_by_external_id
                    END
                )
            """
        )
    )


def _upgrade_candidate_journey(conn: Connection) -> None:
    _add_column_if_missing(
        conn,
        "candidate_journey_sessions",
        "session_version INTEGER NOT NULL DEFAULT 1",
        "session_version",
    )
    if table_exists(conn, "candidate_journey_sessions"):
        conn.execute(
            sa.text(
                """
                UPDATE candidate_journey_sessions
                SET session_version = COALESCE(session_version, 1)
                """
            )
        )


def _upgrade_outbox(conn: Connection) -> None:
    if not table_exists(conn, "outbox_notifications"):
        return

    _add_column_if_missing(conn, "outbox_notifications", "failure_class VARCHAR(32)", "failure_class")
    _add_column_if_missing(conn, "outbox_notifications", "failure_code VARCHAR(64)", "failure_code")
    _add_column_if_missing(conn, "outbox_notifications", "provider_message_id VARCHAR(128)", "provider_message_id")
    _add_column_if_missing(conn, "outbox_notifications", "dead_lettered_at TIMESTAMP", "dead_lettered_at")
    _add_column_if_missing(conn, "outbox_notifications", "last_channel_attempted VARCHAR(20)", "last_channel_attempted")

    if not index_exists(conn, "outbox_notifications", "ix_outbox_channel_status_retry"):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_outbox_channel_status_retry "
                "ON outbox_notifications (messenger_channel, status, next_retry_at)"
            )
        )

    conn.execute(
        sa.text(
            """
            UPDATE outbox_notifications
            SET last_channel_attempted = COALESCE(NULLIF(TRIM(last_channel_attempted), ''), messenger_channel)
            WHERE messenger_channel IS NOT NULL
            """
        )
    )


def _upgrade_notification_logs(conn: Connection) -> None:
    if not table_exists(conn, "notification_logs"):
        return

    _add_column_if_missing(conn, "notification_logs", "channel VARCHAR(20) NOT NULL DEFAULT 'telegram'", "channel")
    _add_column_if_missing(conn, "notification_logs", "failure_class VARCHAR(32)", "failure_class")
    _add_column_if_missing(conn, "notification_logs", "provider_message_id VARCHAR(128)", "provider_message_id")
    _add_column_if_missing(conn, "notification_logs", "attempt_no INTEGER NOT NULL DEFAULT 1", "attempt_no")

    conn.execute(
        sa.text(
            """
            UPDATE notification_logs
            SET channel = COALESCE(NULLIF(TRIM(channel), ''), 'telegram')
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE notification_logs
            SET attempt_no = COALESCE(attempt_no, attempts)
            """
        )
    )


def upgrade(conn: Connection) -> None:
    _upgrade_candidate_invites(conn)
    _upgrade_candidate_journey(conn)
    _upgrade_outbox(conn)
    _upgrade_notification_logs(conn)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name != "postgresql":
        return

    if index_exists(conn, "candidate_invite_tokens", "uq_candidate_invite_tokens_active_max_candidate"):
        conn.execute(sa.text("DROP INDEX IF EXISTS uq_candidate_invite_tokens_active_max_candidate"))

    for table_name, columns in (
        (
            "candidate_invite_tokens",
            ("status", "channel", "superseded_at", "used_by_external_id"),
        ),
        ("candidate_journey_sessions", ("session_version",)),
        (
            "outbox_notifications",
            (
                "failure_class",
                "failure_code",
                "provider_message_id",
                "dead_lettered_at",
                "last_channel_attempted",
            ),
        ),
        ("notification_logs", ("channel", "failure_class", "provider_message_id", "attempt_no")),
    ):
        for column_name in columns:
            if column_exists(conn, table_name, column_name):
                conn.execute(sa.text(f"ALTER TABLE {table_name} DROP COLUMN {column_name}"))
