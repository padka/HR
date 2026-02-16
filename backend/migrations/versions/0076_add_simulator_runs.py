"""Add simulator runs/steps tables for local scenario runner."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0076_add_simulator_runs"
down_revision = "0075_add_kb_and_ai_chat"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, "simulator_runs"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE simulator_runs (
                        id INTEGER PRIMARY KEY,
                        scenario TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'running',
                        started_at TIMESTAMP,
                        finished_at TIMESTAMP,
                        summary_json TEXT NOT NULL DEFAULT '{}',
                        created_by_type TEXT NOT NULL DEFAULT 'admin',
                        created_by_id INTEGER NOT NULL DEFAULT -1
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE simulator_runs (
                        id SERIAL PRIMARY KEY,
                        scenario VARCHAR(64) NOT NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'running',
                        started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        finished_at TIMESTAMP WITH TIME ZONE,
                        summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_by_type VARCHAR(16) NOT NULL DEFAULT 'admin',
                        created_by_id INTEGER NOT NULL DEFAULT -1
                    )
                    """
                )
            )

        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_simulator_runs_status_started "
                "ON simulator_runs (status, started_at)"
            )
        )
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_simulator_runs_created_by "
                "ON simulator_runs (created_by_type, created_by_id, started_at)"
            )
        )

    if not table_exists(conn, "simulator_steps"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE simulator_steps (
                        id INTEGER PRIMARY KEY,
                        run_id INTEGER NOT NULL,
                        step_order INTEGER NOT NULL DEFAULT 0,
                        step_key TEXT NOT NULL,
                        title TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'success',
                        started_at TIMESTAMP,
                        finished_at TIMESTAMP,
                        duration_ms INTEGER NOT NULL DEFAULT 0,
                        details_json TEXT NOT NULL DEFAULT '{}',
                        FOREIGN KEY(run_id) REFERENCES simulator_runs(id) ON DELETE CASCADE
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE simulator_steps (
                        id SERIAL PRIMARY KEY,
                        run_id INTEGER NOT NULL REFERENCES simulator_runs(id) ON DELETE CASCADE,
                        step_order INTEGER NOT NULL DEFAULT 0,
                        step_key VARCHAR(64) NOT NULL,
                        title VARCHAR(200) NOT NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'success',
                        started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        finished_at TIMESTAMP WITH TIME ZONE,
                        duration_ms INTEGER NOT NULL DEFAULT 0,
                        details_json JSONB NOT NULL DEFAULT '{}'::jsonb
                    )
                    """
                )
            )

        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_simulator_steps_run_order "
                "ON simulator_steps (run_id, step_order)"
            )
        )
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_simulator_steps_status "
                "ON simulator_steps (status)"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    conn.execute(sa.text("DROP TABLE IF EXISTS simulator_steps"))
    conn.execute(sa.text("DROP TABLE IF EXISTS simulator_runs"))
