"""Add weekly KPI snapshot table and supporting indexes."""

from __future__ import annotations

import sqlalchemy as sa

revision = "0015_add_kpi_weekly_table"
down_revision = "0014_notification_outbox_and_templates"


def upgrade(conn):
    conn.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS kpi_weekly (
                week_start DATE PRIMARY KEY,
                tested INTEGER NOT NULL DEFAULT 0,
                completed_test INTEGER NOT NULL DEFAULT 0,
                booked INTEGER NOT NULL DEFAULT 0,
                confirmed INTEGER NOT NULL DEFAULT 0,
                interview_passed INTEGER NOT NULL DEFAULT 0,
                intro_day INTEGER NOT NULL DEFAULT 0,
                computed_at TIMESTAMP WITH TIME ZONE NOT NULL
            )
            """
        )
    )

    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_test_results_created_at ON test_results (created_at)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_slots_updated_at ON slots (updated_at)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_slots_status ON slots (status)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_slots_purpose ON slots (purpose)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_slots_interview_outcome ON slots (interview_outcome)"
        )
    )


def downgrade(conn):  # pragma: no cover - maintenance helper
    conn.execute(sa.text("DROP TABLE IF EXISTS kpi_weekly"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_test_results_created_at"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_slots_updated_at"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_slots_status"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_slots_purpose"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_slots_interview_outcome"))
