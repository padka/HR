"""Add intro day details fields to slots."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "0025_add_intro_day_details"
down_revision = "0024_remove_legacy_24h_reminders"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    inspector = inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("slots")}

    if "intro_address" not in columns:
        conn.execute(text("ALTER TABLE slots ADD COLUMN intro_address TEXT"))
    if "intro_contact" not in columns:
        conn.execute(text("ALTER TABLE slots ADD COLUMN intro_contact TEXT"))


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    if conn.dialect.name == "sqlite":
        # SQLite lacks DROP COLUMN support prior to 3.35.0; skipping keeps migration reversible elsewhere.
        return

    inspector = inspect(conn)
    columns = {column["name"] for column in inspector.get_columns("slots")}

    if "intro_contact" in columns:
        conn.execute(text("ALTER TABLE slots DROP COLUMN intro_contact"))
    if "intro_address" in columns:
        conn.execute(text("ALTER TABLE slots DROP COLUMN intro_address"))
