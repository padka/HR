"""Prevent duplicate reservations per recruiter."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "0007_prevent_duplicate_slot_reservations"
down_revision = "0006_add_slots_recruiter_start_index"
branch_labels = None
depends_on = None


UNIQUE_INDEX_NAME = "uq_slots_candidate_recruiter_active"
LOCKS_TABLE = "slot_reservation_locks"
LOCKS_INDEX = "uq_slot_reservation_locks_key"


def upgrade(conn: Connection) -> None:
    conn.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS {LOCKS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
                candidate_tg_id BIGINT NOT NULL,
                recruiter_id INTEGER NOT NULL REFERENCES recruiters(id) ON DELETE CASCADE,
                reservation_date DATE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT (CURRENT_TIMESTAMP)
            )
            """
        )
    )

    conn.execute(
        sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {LOCKS_INDEX} "
            f"ON {LOCKS_TABLE} (candidate_tg_id, recruiter_id, reservation_date)"
        )
    )

    conn.execute(
        sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {UNIQUE_INDEX_NAME} "
            "ON slots (candidate_tg_id, recruiter_id) "
            "WHERE lower(status) IN ('pending', 'booked')"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - symmetry only
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {UNIQUE_INDEX_NAME}"))
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {LOCKS_INDEX}"))
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {LOCKS_TABLE}"))

