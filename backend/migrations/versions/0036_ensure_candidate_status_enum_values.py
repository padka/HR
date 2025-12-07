"""Ensure candidate_status_enum has all values from Python Enum.

This migration ensures the PostgreSQL ENUM type contains all status values
defined in backend.domain.candidates.status.CandidateStatus.

Revision ID: 0036_ensure_candidate_status_enum_values
Revises: 0035_add_analytics_events_and_jinja_flag
Create Date: 2025-12-07 17:50:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0036_ensure_candidate_status_enum_values"
down_revision = "0035_add_analytics_events_and_jinja_flag"
branch_labels = None
depends_on = None


# All values that should exist in the ENUM (in order)
REQUIRED_ENUM_VALUES = [
    "test1_completed",
    "waiting_slot",
    "stalled_waiting_slot",
    "interview_scheduled",
    "interview_confirmed",
    "interview_declined",
    "test2_sent",
    "test2_completed",
    "test2_failed",
    "intro_day_scheduled",
    "intro_day_confirmed_preliminary",
    "intro_day_declined_invitation",
    "intro_day_confirmed_day_of",
    "intro_day_declined_day_of",
    "hired",
    "not_hired",
]


def upgrade(conn: Connection) -> None:
    """Add missing values to candidate_status_enum."""

    # Check if enum type exists
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'candidate_status_enum'
        )
    """))
    enum_exists = result.scalar()

    if not enum_exists:
        # If enum doesn't exist, migration 0022 will create it
        return

    # Get existing enum values
    result = conn.execute(sa.text("""
        SELECT enumlabel FROM pg_enum
        WHERE enumtypid = 'candidate_status_enum'::regtype
        ORDER BY enumsortorder
    """))
    existing_values = {row[0] for row in result}

    # Add missing values
    for value in REQUIRED_ENUM_VALUES:
        if value not in existing_values:
            # Use DO block to add value if it doesn't exist
            # Note: ALTER TYPE ADD VALUE cannot run inside a transaction block in some PG versions,
            # but we're using IF NOT EXISTS pattern which is safe
            conn.execute(sa.text(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_enum
                        WHERE enumtypid = 'candidate_status_enum'::regtype
                        AND enumlabel = '{value}'
                    ) THEN
                        ALTER TYPE candidate_status_enum ADD VALUE '{value}';
                    END IF;
                END
                $$;
            """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Downgrade not supported for enum values.

    PostgreSQL doesn't support removing enum values.
    To downgrade, you would need to:
    1. Remove all usages of the new values from tables
    2. Drop and recreate the enum type
    3. Update all tables using the enum
    """
    pass
