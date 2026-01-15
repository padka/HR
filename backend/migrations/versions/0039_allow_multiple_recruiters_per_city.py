"""Allow attaching multiple recruiters to a single city."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists


revision = "0039_allow_multiple_recruiters_per_city"
down_revision = "0038_recruiter_user_profile_link"
branch_labels = None
depends_on = None


TABLE_NAME = "recruiter_cities"
CONSTRAINT_NAME = "uq_recruiter_city_unique_city"


def upgrade(conn: Connection) -> None:
    """Drop city-only uniqueness to permit multiple recruiters per city."""
    if not table_exists(conn, TABLE_NAME):
        return
    conn.execute(sa.text(f"ALTER TABLE {TABLE_NAME} DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Recreate the original constraint enforcing single recruiter per city."""
    if not table_exists(conn, TABLE_NAME):
        return
    conn.execute(
        sa.text(
            f"ALTER TABLE {TABLE_NAME} ADD CONSTRAINT {CONSTRAINT_NAME} UNIQUE (city_id)"
        )
    )
