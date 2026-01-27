"""Add recruiter plan entries for manual city plan tracking."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy import inspect

revision = "0059_add_recruiter_plan_entries"
down_revision = "0058_add_recruiter_last_seen_at"
branch_labels = None
depends_on = None


def _table_exists(conn: Connection, table: str) -> bool:
    inspector = inspect(conn)
    try:
        return table in inspector.get_table_names()
    except Exception:
        return False


def upgrade(conn: Connection) -> None:
    if _table_exists(conn, "recruiter_plan_entries"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                """
                CREATE TABLE recruiter_plan_entries (
                    id INTEGER PRIMARY KEY,
                    recruiter_id INTEGER NOT NULL REFERENCES recruiters(id) ON DELETE CASCADE,
                    city_id INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
                    last_name TEXT NOT NULL,
                    created_at TIMESTAMP
                )
                """
            )
        )
    else:
        conn.execute(
            sa.text(
                """
                CREATE TABLE recruiter_plan_entries (
                    id SERIAL PRIMARY KEY,
                    recruiter_id INTEGER NOT NULL REFERENCES recruiters(id) ON DELETE CASCADE,
                    city_id INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
                    last_name VARCHAR(120) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )
        )

    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_recruiter_plan_entries_recruiter_city "
            "ON recruiter_plan_entries (recruiter_id, city_id)"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    conn.execute(sa.text("DROP TABLE IF EXISTS recruiter_plan_entries"))
