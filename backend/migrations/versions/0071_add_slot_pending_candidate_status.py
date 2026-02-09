"""Add slot_pending to candidate_status_enum."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0071_add_slot_pending_candidate_status"
down_revision = "0070_add_city_intro_fields"
branch_labels = None
depends_on = None


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

    conn.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum
                    WHERE enumtypid = 'candidate_status_enum'::regtype
                    AND enumlabel = 'slot_pending'
                ) THEN
                    ALTER TYPE candidate_status_enum ADD VALUE 'slot_pending';
                END IF;
            END
            $$;
            """
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    pass
