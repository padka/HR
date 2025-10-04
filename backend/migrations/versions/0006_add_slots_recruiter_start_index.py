"""Add composite index on slots recruiter and start time."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "0006_add_slots_recruiter_start_index"
down_revision = "0005_add_city_profile_fields"
branch_labels = None
depends_on = None


INDEX_NAME = "ix_slots_recruiter_start"


def upgrade(conn: Connection) -> None:
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS "
            f"{INDEX_NAME} ON slots (recruiter_id, start_utc)"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry only
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))

