"""Add detailization_entries table for intro day reporting."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0077_add_detailization_entries"
down_revision = "0076_add_simulator_runs"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if table_exists(conn, "detailization_entries"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                """
                CREATE TABLE detailization_entries (
                    id INTEGER PRIMARY KEY,
                    slot_assignment_id INTEGER,
                    slot_id INTEGER,
                    candidate_id INTEGER NOT NULL,
                    recruiter_id INTEGER,
                    city_id INTEGER,
                    assigned_at TIMESTAMP,
                    conducted_at TIMESTAMP,
                    expert_name TEXT,
                    column_9 TEXT,
                    is_attached BOOLEAN,
                    created_by_type TEXT NOT NULL DEFAULT 'system',
                    created_by_id INTEGER NOT NULL DEFAULT -1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY(slot_assignment_id) REFERENCES slot_assignments(id) ON DELETE SET NULL,
                    FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE SET NULL,
                    FOREIGN KEY(candidate_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(recruiter_id) REFERENCES recruiters(id) ON DELETE SET NULL,
                    FOREIGN KEY(city_id) REFERENCES cities(id) ON DELETE SET NULL
                )
                """
            )
        )
    else:
        conn.execute(
            sa.text(
                """
                CREATE TABLE detailization_entries (
                    id SERIAL PRIMARY KEY,
                    slot_assignment_id INTEGER REFERENCES slot_assignments(id) ON DELETE SET NULL,
                    slot_id INTEGER REFERENCES slots(id) ON DELETE SET NULL,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    recruiter_id INTEGER REFERENCES recruiters(id) ON DELETE SET NULL,
                    city_id INTEGER REFERENCES cities(id) ON DELETE SET NULL,
                    assigned_at TIMESTAMP WITH TIME ZONE,
                    conducted_at TIMESTAMP WITH TIME ZONE,
                    expert_name VARCHAR(160),
                    column_9 TEXT,
                    is_attached BOOLEAN,
                    created_by_type VARCHAR(16) NOT NULL DEFAULT 'system',
                    created_by_id INTEGER NOT NULL DEFAULT -1,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )
        )

    conn.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_detailization_slot_assignment "
            "ON detailization_entries (slot_assignment_id)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_detailization_entries_conducted_at "
            "ON detailization_entries (conducted_at)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_detailization_entries_recruiter_conducted_at "
            "ON detailization_entries (recruiter_id, conducted_at)"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    conn.execute(sa.text("DROP TABLE IF EXISTS detailization_entries"))

