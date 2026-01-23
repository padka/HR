"""Add performance indexes for slots and users tables.

These indexes optimize common query patterns:
- slots: status filtering, recruiter+time range queries, candidate lookups
- users: workflow_status filtering, recruiter assignment lookups
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0055_add_performance_indexes"
down_revision = "0054_restore_city_responsible_recruiter"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    # Slots table indexes
    if table_exists(conn, "slots"):
        # Index for status filtering (e.g., WHERE status='free')
        conn.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS ix_slots_status
                ON slots (status)
                """
            )
        )

        # Composite index for recruiter schedule queries
        # (e.g., WHERE recruiter_id=X AND start_utc BETWEEN ...)
        conn.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS ix_slots_recruiter_start
                ON slots (recruiter_id, start_utc)
                """
            )
        )

        # Index for candidate slot lookups
        conn.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS ix_slots_candidate_id
                ON slots (candidate_id)
                WHERE candidate_id IS NOT NULL
                """
            )
        )

    # Users table indexes
    if table_exists(conn, "users"):
        # Index for workflow status filtering
        conn.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS ix_users_workflow_status
                ON users (workflow_status)
                WHERE workflow_status IS NOT NULL
                """
            )
        )

        # Index for recruiter assignment lookups
        conn.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS ix_users_responsible_recruiter
                ON users (responsible_recruiter_id)
                WHERE responsible_recruiter_id IS NOT NULL
                """
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if table_exists(conn, "users"):
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_responsible_recruiter"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_workflow_status"))

    if table_exists(conn, "slots"):
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_slots_candidate_id"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_slots_recruiter_start"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_slots_status"))
