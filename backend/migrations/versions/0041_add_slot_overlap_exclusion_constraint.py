"""Add exclusion constraint to prevent overlapping slots for the same recruiter.

This migration adds a PostgreSQL exclusion constraint using btree_gist extension
to ensure that slots for the same recruiter cannot overlap in time.
The constraint checks that for any recruiter_id, the time ranges [start_utc, end_utc)
do not overlap.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from backend.migrations.utils import table_exists

revision = "0041_add_slot_overlap_exclusion_constraint"
down_revision = "0040_add_audit_log_table"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "slots_no_recruiter_time_overlap_excl"
logger = logging.getLogger(__name__)


def upgrade(conn: Connection) -> None:
    """Add exclusion constraint to prevent overlapping slots."""
    if not table_exists(conn, "slots"):
        return

    # Enable btree_gist extension if not already enabled (required for exclusion constraints)
    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))

    # Create an IMMUTABLE helper function to compute slot end time
    # This is required because exclusion constraints need IMMUTABLE expressions
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

    # Check if constraint already exists
    result = conn.execute(
        sa.text(
            """
            SELECT 1 FROM pg_constraint
            WHERE conname = :constraint_name
            """
        ),
        {"constraint_name": CONSTRAINT_NAME},
    )
    if result.fetchone() is not None:
        return  # Constraint already exists

    # Add exclusion constraint
    # This ensures that for the same recruiter_id, time ranges cannot overlap
    # The range is computed as [start_utc, slot_end_time(start_utc, duration_min))
    try:
        conn.execute(
            sa.text(
                f"""
                ALTER TABLE slots
                ADD CONSTRAINT {CONSTRAINT_NAME}
                EXCLUDE USING gist (
                    recruiter_id WITH =,
                    tstzrange(start_utc, slot_end_time(start_utc, duration_min)) WITH &&
                )
                """
            )
        )
    except IntegrityError:
        # Back-compat for existing production data that may already contain overlaps.
        # We skip constraint creation to unblock deployment and keep revision chain
        # consistent. Overlap checks are still enforced at application level.
        logger.warning(
            "Skipping %s creation because existing slot data has overlaps. "
            "Constraint can be added after data cleanup.",
            CONSTRAINT_NAME,
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Remove exclusion constraint and helper function."""
    if not table_exists(conn, "slots"):
        return

    conn.execute(
        sa.text(f"ALTER TABLE slots DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}")
    )

    conn.execute(sa.text("DROP FUNCTION IF EXISTS slot_end_time(timestamptz, integer)"))
