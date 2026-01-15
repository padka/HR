"""Enforce slot overlap check on fixed 10-minute windows.

This migration recreates the exclusion constraint so that overlap is checked
against [start, start + 10 minutes) regardless of stored duration.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0051_enforce_slot_overlap_on_10min_windows"
down_revision = "0050_align_slot_overlap_bounds_and_duration_default"
branch_labels = None
depends_on = None

TABLE = "slots"
CONSTRAINT_NAME = "slots_no_recruiter_time_overlap_excl"


def upgrade(conn: Connection) -> None:
    if conn.dialect.name != "postgresql":
        return
    if not table_exists(conn, TABLE):
        return

    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    # Use fixed 10 minute windows to allow dense schedules.
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION slot_end_time(start_utc timestamptz, duration_min integer)
            RETURNS timestamptz
            AS $$
                SELECT start_utc + interval '10 minute'
            $$
            LANGUAGE SQL IMMUTABLE PARALLEL SAFE
            """
        )
    )

    conn.execute(sa.text(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"))
    conn.execute(
        sa.text(
            f"""
            ALTER TABLE {TABLE}
            ADD CONSTRAINT {CONSTRAINT_NAME}
            EXCLUDE USING gist (
                recruiter_id WITH =,
                tstzrange(start_utc, slot_end_time(start_utc, duration_min), '[)') WITH &&
            )
            """
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name != "postgresql":
        return
    if not table_exists(conn, TABLE):
        return

    conn.execute(sa.text(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"))
    conn.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION slot_end_time(start_utc timestamptz, duration_min integer)
            RETURNS timestamptz
            AS $$
                SELECT start_utc + (duration_min * interval '1 minute')
            $$
            LANGUAGE SQL IMMUTABLE PARALLEL SAFE
            """
        )
    )
    conn.execute(
        sa.text(
            f"""
            ALTER TABLE {TABLE}
            ADD CONSTRAINT {CONSTRAINT_NAME}
            EXCLUDE USING gist (
                recruiter_id WITH =,
                tstzrange(start_utc, slot_end_time(start_utc, duration_min), '[)') WITH &&
            )
            """
        )
    )
