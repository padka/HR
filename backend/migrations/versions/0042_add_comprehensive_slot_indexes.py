"""Add comprehensive indexes for slot queries optimization.

This migration adds indexes for common slot query patterns:
- Free slots by city (for candidate slot selection)
- Slots by candidate (for candidate's booked slots)
- Admin panel queries (recruiter + status + time)
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, index_exists

revision = "0042_add_comprehensive_slot_indexes"
down_revision = "0041_add_slot_overlap_exclusion_constraint"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Add indexes for common slot query patterns."""
    if not table_exists(conn, "slots"):
        return

    # Index 1: Free slots by city - partial index for candidate slot selection
    # This supports queries like: "find free slots in city X"
    index_name = "ix_slots_city_free_start"
    if not index_exists(conn, "slots", index_name):
        conn.execute(
            sa.text(
                f"""
                CREATE INDEX {index_name}
                ON slots (city_id, start_utc)
                WHERE lower(status) = 'free'
                """
            )
        )

    # Index 2: Slots by candidate - for finding candidate's booked slots
    # This supports queries like: "find all slots for candidate X"
    index_name = "ix_slots_candidate_start"
    if not index_exists(conn, "slots", index_name):
        conn.execute(
            sa.text(
                f"""
                CREATE INDEX {index_name}
                ON slots (candidate_tg_id, start_utc DESC)
                WHERE candidate_tg_id IS NOT NULL
                """
            )
        )

    # Index 3: Admin panel queries - recruiter + status + time DESC
    # This supports queries like: "show me all slots for recruiter X, ordered by time"
    index_name = "ix_slots_recruiter_status_start_desc"
    if not index_exists(conn, "slots", index_name):
        conn.execute(
            sa.text(
                f"""
                CREATE INDEX {index_name}
                ON slots (recruiter_id, status, start_utc DESC)
                """
            )
        )

    # Index 4: City slots with status - for admin filtering
    # This supports queries like: "show all slots in city X with status Y"
    index_name = "ix_slots_city_status_start"
    if not index_exists(conn, "slots", index_name):
        conn.execute(
            sa.text(
                f"""
                CREATE INDEX {index_name}
                ON slots (city_id, status, start_utc)
                WHERE city_id IS NOT NULL
                """
            )
        )

    # Note: We don't add a partial index for "upcoming slots" because
    # CURRENT_TIMESTAMP is not IMMUTABLE and cannot be used in index predicates.
    # The composite indexes above will be sufficient for most queries.


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Remove the indexes."""
    if not table_exists(conn, "slots"):
        return

    indexes = [
        "ix_slots_city_free_start",
        "ix_slots_candidate_start",
        "ix_slots_recruiter_status_start_desc",
        "ix_slots_city_status_start",
    ]

    for index_name in indexes:
        if index_exists(conn, "slots", index_name):
            conn.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
