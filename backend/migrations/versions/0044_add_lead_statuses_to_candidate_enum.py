"""Add lead-stage statuses to candidate_status_enum."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0044_add_lead_statuses_to_candidate_enum"
down_revision = "0043_add_candidate_uuid_and_lead_source"
branch_labels = None
depends_on = None


REQUIRED_ENUM_VALUES = [
    "lead",
    "contacted",
    "invited",
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
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'candidate_status_enum'
            )
            """
        )
    )
    enum_exists = result.scalar()
    if not enum_exists:
        return

    result = conn.execute(
        sa.text(
            """
            SELECT enumlabel FROM pg_enum
            WHERE enumtypid = 'candidate_status_enum'::regtype
            ORDER BY enumsortorder
            """
        )
    )
    existing_values = {row[0] for row in result}

    for value in REQUIRED_ENUM_VALUES:
        if value not in existing_values:
            conn.execute(
                sa.text(
                    f"""
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
                    """
                )
            )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    pass
