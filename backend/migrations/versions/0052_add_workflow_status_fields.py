"""Add workflow status fields for candidate state-machine."""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0052_add_workflow_status_fields"
down_revision = "0051_enforce_slot_overlap_on_10min_windows"
branch_labels = None
depends_on = None

TABLE = "users"


def upgrade(conn: Connection) -> None:
    if not table_exists(conn, TABLE):
        return

    conn.execute(sa.text(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS workflow_status VARCHAR(64)"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS rejection_stage VARCHAR(64)"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS rejected_by VARCHAR(120)"))

    conn.execute(
        sa.text(
            f"""
            UPDATE {TABLE}
            SET workflow_status = 'WAITING_FOR_SLOT',
                status_changed_at = COALESCE(status_changed_at, :now)
            WHERE workflow_status IS NULL
            """
        ),
        {"now": datetime.now(timezone.utc)},
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if not table_exists(conn, TABLE):
        return
    conn.execute(sa.text(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS rejected_by"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS rejected_at"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS rejection_stage"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS workflow_status"))
