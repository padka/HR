"""Align slot overlap constraint bounds and default slot duration.

This migration explicitly sets the slot overlap exclusion constraint to use
half-open ranges [start, end) and updates the default slot duration to 10 minutes
for newly created slots.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, table_exists

revision = "0050_align_slot_overlap_bounds_and_duration_default"
down_revision = "0049_allow_null_city_timezone"
branch_labels = None
depends_on = None

TABLE = "slots"
CONSTRAINT_NAME = "slots_no_recruiter_time_overlap_excl"
DEFAULT_DURATION = 10
LEGACY_DEFAULT_DURATION = 60


def _set_duration_default(conn: Connection, default: int) -> None:
    if conn.dialect.name == "sqlite":
        return
    if not column_exists(conn, TABLE, "duration_min"):
        return
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ALTER COLUMN duration_min SET DEFAULT {default}"))


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, TABLE):
        return

    _set_duration_default(conn, DEFAULT_DURATION)

    if conn.dialect.name != "postgresql":
        return

    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
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
    if not table_exists(conn, TABLE):
        return

    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"))
        conn.execute(
            sa.text(
                f"""
                ALTER TABLE {TABLE}
                ADD CONSTRAINT {CONSTRAINT_NAME}
                EXCLUDE USING gist (
                    recruiter_id WITH =,
                    tstzrange(start_utc, slot_end_time(start_utc, duration_min)) WITH &&
                )
                """
            )
        )

    _set_duration_default(conn, LEGACY_DEFAULT_DURATION)
