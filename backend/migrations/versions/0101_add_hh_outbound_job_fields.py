"""Add candidate-bound outbound result fields to HH sync jobs."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists

revision = "0101_add_hh_outbound_job_fields"
down_revision = "0099a_refresh_interview_confirmation_copy"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if not column_exists(conn, "hh_sync_jobs", "candidate_id"):
        conn.execute(sa.text("ALTER TABLE hh_sync_jobs ADD COLUMN candidate_id INTEGER"))
    if not column_exists(conn, "hh_sync_jobs", "result_json"):
        conn.execute(sa.text("ALTER TABLE hh_sync_jobs ADD COLUMN result_json JSON"))
    if not column_exists(conn, "hh_sync_jobs", "failure_code"):
        conn.execute(sa.text("ALTER TABLE hh_sync_jobs ADD COLUMN failure_code VARCHAR(64)"))

    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_hh_sync_jobs_candidate "
            "ON hh_sync_jobs(candidate_id, status)"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_hh_sync_jobs_candidate"))
        if column_exists(conn, "hh_sync_jobs", "failure_code"):
            conn.execute(sa.text("ALTER TABLE hh_sync_jobs DROP COLUMN failure_code"))
        if column_exists(conn, "hh_sync_jobs", "result_json"):
            conn.execute(sa.text("ALTER TABLE hh_sync_jobs DROP COLUMN result_json"))
        if column_exists(conn, "hh_sync_jobs", "candidate_id"):
            conn.execute(sa.text("ALTER TABLE hh_sync_jobs DROP COLUMN candidate_id"))
