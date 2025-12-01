"""Add manual slot availability fields to users."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0029_add_manual_slot_availability"
down_revision = "0028_add_candidate_profile_fields"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    dialect = conn.dialect.name
    ts_col = "TIMESTAMP WITH TIME ZONE"
    if dialect == "sqlite":
        ts_col = "TIMESTAMP"

    conn.execute(sa.text(f"ALTER TABLE users ADD COLUMN manual_slot_from {ts_col}"))
    conn.execute(sa.text(f"ALTER TABLE users ADD COLUMN manual_slot_to {ts_col}"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN manual_slot_comment TEXT"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN manual_slot_timezone VARCHAR(64)"))
    conn.execute(sa.text(f"ALTER TABLE users ADD COLUMN manual_slot_requested_at {ts_col}"))
    conn.execute(sa.text(f"ALTER TABLE users ADD COLUMN manual_slot_response_at {ts_col}"))


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    if conn.dialect.name == "sqlite":
        # SQLite lacks reliable DROP COLUMN support on older versions
        return

    conn.execute(sa.text("ALTER TABLE users DROP COLUMN manual_slot_response_at"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN manual_slot_requested_at"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN manual_slot_timezone"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN manual_slot_comment"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN manual_slot_to"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN manual_slot_from"))
