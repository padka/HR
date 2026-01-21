"""Add indexes to outbox_notifications for efficient queue processing.

Without indexes, queries like SELECT WHERE status='pending' ORDER BY created_at
perform full table scans, which degrades performance under load.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0053_add_outbox_notification_indexes"
down_revision = "0052_add_workflow_status_fields"
branch_labels = None
depends_on = None

TABLE = "outbox_notifications"


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, TABLE):
        return

    # Index for queue processing: SELECT WHERE status='pending' ORDER BY created_at
    conn.execute(
        sa.text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_outbox_status_created
            ON {TABLE} (status, created_at)
            """
        )
    )

    # Index for retry logic: SELECT WHERE status='pending' AND next_retry_at <= NOW()
    conn.execute(
        sa.text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_outbox_status_retry
            ON {TABLE} (status, next_retry_at)
            WHERE next_retry_at IS NOT NULL
            """
        )
    )

    # Index for correlation lookups
    conn.execute(
        sa.text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_outbox_correlation
            ON {TABLE} (correlation_id)
            WHERE correlation_id IS NOT NULL
            """
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if not table_exists(conn, TABLE):
        return
    conn.execute(sa.text(f"DROP INDEX IF EXISTS ix_outbox_correlation"))
    conn.execute(sa.text(f"DROP INDEX IF EXISTS ix_outbox_status_retry"))
    conn.execute(sa.text(f"DROP INDEX IF EXISTS ix_outbox_status_created"))
