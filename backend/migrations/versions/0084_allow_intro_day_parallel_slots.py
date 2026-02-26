"""Allow parallel intro-day slots at the same time.

Keeps overlap and active-slot uniqueness limits for interview flow,
but excludes intro_day slots from these limits.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from backend.migrations.utils import table_exists

revision = "0084_allow_intro_day_parallel_slots"
down_revision = "0083_sync_test1_question_bank"
branch_labels = None
depends_on = None

TABLE = "slots"
OVERLAP_CONSTRAINT = "slots_no_recruiter_time_overlap_excl"
ACTIVE_UNIQUE_INDEX = "uq_slots_candidate_recruiter_purpose_active"

logger = logging.getLogger(__name__)


def _ensure_slot_end_function(conn: Connection) -> None:
    if conn.dialect.name != "postgresql":
        return
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


def _rebuild_active_unique_index_excluding_intro_day(conn: Connection) -> None:
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {ACTIVE_UNIQUE_INDEX}"))
    conn.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {ACTIVE_UNIQUE_INDEX}
                ON {TABLE} (candidate_tg_id, recruiter_id, purpose)
             WHERE lower(status) IN ('pending','booked','confirmed_by_candidate')
               AND lower(coalesce(purpose, 'interview')) <> 'intro_day'
            """
        )
    )


def _rebuild_active_unique_index_default(conn: Connection) -> None:
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {ACTIVE_UNIQUE_INDEX}"))
    conn.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {ACTIVE_UNIQUE_INDEX}
                ON {TABLE} (candidate_tg_id, recruiter_id, purpose)
             WHERE lower(status) IN ('pending','booked','confirmed_by_candidate')
            """
        )
    )


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, TABLE):
        return

    _rebuild_active_unique_index_excluding_intro_day(conn)

    if conn.dialect.name != "postgresql":
        return

    _ensure_slot_end_function(conn)

    savepoint = conn.begin_nested()
    try:
        conn.execute(
            sa.text(
                f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {OVERLAP_CONSTRAINT}"
            )
        )
        conn.execute(
            sa.text(
                f"""
                ALTER TABLE {TABLE}
                ADD CONSTRAINT {OVERLAP_CONSTRAINT}
                EXCLUDE USING gist (
                    recruiter_id WITH =,
                    purpose WITH =,
                    tstzrange(start_utc, slot_end_time(start_utc, duration_min), '[)') WITH &&
                )
                WHERE (lower(coalesce(purpose, 'interview')) <> 'intro_day')
                """
            )
        )
    except IntegrityError:
        savepoint.rollback()
        logger.warning(
            "Skipping %s recreation in %s due conflicting data.",
            OVERLAP_CONSTRAINT,
            revision,
        )
    else:
        savepoint.commit()


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if not table_exists(conn, TABLE):
        return

    _rebuild_active_unique_index_default(conn)

    if conn.dialect.name != "postgresql":
        return

    _ensure_slot_end_function(conn)

    savepoint = conn.begin_nested()
    try:
        conn.execute(
            sa.text(
                f"ALTER TABLE {TABLE} DROP CONSTRAINT IF EXISTS {OVERLAP_CONSTRAINT}"
            )
        )
        conn.execute(
            sa.text(
                f"""
                ALTER TABLE {TABLE}
                ADD CONSTRAINT {OVERLAP_CONSTRAINT}
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
            "Skipping %s downgrade recreation in %s due conflicting data.",
            OVERLAP_CONSTRAINT,
            revision,
        )
    else:
        savepoint.commit()
