"""Allow overlapping slots across different purposes for the same recruiter.

Rebuilds the exclusion constraint so overlap is checked per
(recruiter_id, purpose, 10-minute window).
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from backend.migrations.utils import table_exists

revision = "0080_slot_overlap_per_purpose"
down_revision = "0079_add_city_reminder_policies"
branch_labels = None
depends_on = None

TABLE = "slots"
CONSTRAINT_NAME = "slots_no_recruiter_time_overlap_excl"
logger = logging.getLogger(__name__)


def _ensure_slot_end_function(conn: Connection) -> None:
    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
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


def upgrade(conn: Connection) -> None:
    if conn.dialect.name != "postgresql":
        return
    if not table_exists(conn, TABLE):
        return

    _ensure_slot_end_function(conn)

    savepoint = conn.begin_nested()
    try:
        conn.execute(sa.text(f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"))
        conn.execute(
            sa.text(
                f"""
                ALTER TABLE {TABLE}
                ADD CONSTRAINT {CONSTRAINT_NAME}
                EXCLUDE USING gist (
                    recruiter_id WITH =,
                    purpose WITH =,
                    tstzrange(start_utc, slot_end_time(start_utc, duration_min), '[)') WITH &&
                )
                """
            )
        )
    except IntegrityError:
        savepoint.rollback()
        logger.warning(
            "Skipping %s recreation in %s because slot data has overlaps. "
            "Constraint can be added after data cleanup.",
            CONSTRAINT_NAME,
            revision,
        )
    else:
        savepoint.commit()


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name != "postgresql":
        return
    if not table_exists(conn, TABLE):
        return

    _ensure_slot_end_function(conn)

    savepoint = conn.begin_nested()
    try:
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
    except IntegrityError:
        savepoint.rollback()
        logger.warning(
            "Skipping %s downgrade recreation in %s because slot data has overlaps.",
            CONSTRAINT_NAME,
            revision,
        )
    else:
        savepoint.commit()
