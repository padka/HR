"""Add recruiter last_seen_at for presence tracking."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy import inspect

revision = "0058_add_recruiter_last_seen_at"
down_revision = "0057_auth_accounts"
branch_labels = None
depends_on = None


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    inspector = inspect(conn)
    try:
        return any(col["name"] == column for col in inspector.get_columns(table))
    except Exception:
        return False


def upgrade(conn: Connection) -> None:
    if not _column_exists(conn, "recruiters", "last_seen_at"):
        ts_col = "TIMESTAMP WITH TIME ZONE"
        if conn.dialect.name == "sqlite":
            ts_col = "TIMESTAMP"
        conn.execute(sa.text(f"ALTER TABLE recruiters ADD COLUMN last_seen_at {ts_col}"))
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_recruiters_last_seen_at ON recruiters (last_seen_at)")
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    if conn.dialect.name == "sqlite":
        return
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_recruiters_last_seen_at"))
    if _column_exists(conn, "recruiters", "last_seen_at"):
        conn.execute(sa.text("ALTER TABLE recruiters DROP COLUMN last_seen_at"))
