"""Add quick-create profile fields to users."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0028_add_candidate_profile_fields"
down_revision = "0027_add_manual_slot_audit_log"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN desired_position VARCHAR(120)"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN resume_filename VARCHAR(255)"))


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    if conn.dialect.name == "sqlite":
        return
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN resume_filename"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN desired_position"))
