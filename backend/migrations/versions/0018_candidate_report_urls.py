"""Add report URLs to candidate profiles."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0018_candidate_report_urls"
down_revision = "0017_bot_message_logs"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN test1_report_url VARCHAR(255)"))
    conn.execute(sa.text("ALTER TABLE users ADD COLUMN test2_report_url VARCHAR(255)"))


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback support
    if conn.dialect.name == "sqlite":
        return
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN test2_report_url"))
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN test1_report_url"))
