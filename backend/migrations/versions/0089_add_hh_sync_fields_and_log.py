"""Add hh.ru sync fields to users table and create hh_sync_log table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, table_exists

revision = "0089_add_hh_sync_fields_and_log"
down_revision = "0088_upgrade_candidate_template_texts"
branch_labels = None
depends_on = None


def _add_hh_fields_to_users(conn: Connection) -> None:
    """Add hh.ru integration columns to the users table."""
    columns = [
        ("hh_resume_id", "VARCHAR(64)"),
        ("hh_negotiation_id", "VARCHAR(64)"),
        ("hh_vacancy_id", "VARCHAR(64)"),
        ("hh_synced_at", "TIMESTAMP" if conn.dialect.name == "sqlite" else "TIMESTAMP WITH TIME ZONE"),
        ("hh_sync_status", "VARCHAR(20)"),
        ("hh_sync_error", "TEXT"),
    ]
    for col_name, col_type in columns:
        if not column_exists(conn, "users", col_name):
            conn.execute(
                sa.text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            )

    # Index on hh_resume_id for fast lookups during resolve
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_users_hh_resume_id "
            "ON users(hh_resume_id)"
        )
    )
    # Index on hh_negotiation_id for sync lookups
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_users_hh_negotiation_id "
            "ON users(hh_negotiation_id)"
        )
    )


def _create_hh_sync_log(conn: Connection) -> None:
    """Create the hh_sync_log audit table."""
    if table_exists(conn, "hh_sync_log"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                """
                CREATE TABLE hh_sync_log (
                    id INTEGER PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    event_type VARCHAR(64) NOT NULL,
                    rs_status VARCHAR(64),
                    hh_status VARCHAR(32),
                    request_payload JSON,
                    response_payload JSON,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    else:
        conn.execute(
            sa.text(
                """
                CREATE TABLE hh_sync_log (
                    id SERIAL PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    event_type VARCHAR(64) NOT NULL,
                    rs_status VARCHAR(64),
                    hh_status VARCHAR(32),
                    request_payload JSON,
                    response_payload JSON,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                """
            )
        )

    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_hh_sync_log_candidate "
            "ON hh_sync_log(candidate_id, created_at)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_hh_sync_log_status "
            "ON hh_sync_log(status)"
        )
    )


def upgrade(conn: Connection) -> None:
    _add_hh_fields_to_users(conn)
    _create_hh_sync_log(conn)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("DROP TABLE IF EXISTS hh_sync_log CASCADE"))
        for col in ("hh_sync_error", "hh_sync_status", "hh_synced_at",
                     "hh_vacancy_id", "hh_negotiation_id", "hh_resume_id"):
            if column_exists(conn, "users", col):
                conn.execute(sa.text(f"ALTER TABLE users DROP COLUMN {col}"))
    else:
        conn.execute(sa.text("DROP TABLE IF EXISTS hh_sync_log"))
