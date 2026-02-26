"""Add city_reminder_policies table for per-city reminder configuration."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists

revision = "0079_add_city_reminder_policies"
down_revision = "0078_add_vacancies"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if table_exists(conn, "city_reminder_policies"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(sa.text("""
            CREATE TABLE city_reminder_policies (
                id INTEGER PRIMARY KEY,
                city_id INTEGER NOT NULL UNIQUE REFERENCES cities(id) ON DELETE CASCADE,
                confirm_6h_enabled BOOLEAN NOT NULL DEFAULT 1,
                confirm_3h_enabled BOOLEAN NOT NULL DEFAULT 1,
                confirm_2h_enabled BOOLEAN NOT NULL DEFAULT 1,
                intro_remind_3h_enabled BOOLEAN NOT NULL DEFAULT 1,
                quiet_hours_start INTEGER NOT NULL DEFAULT 22,
                quiet_hours_end INTEGER NOT NULL DEFAULT 8,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    else:
        conn.execute(sa.text("""
            CREATE TABLE city_reminder_policies (
                id SERIAL PRIMARY KEY,
                city_id INTEGER NOT NULL UNIQUE REFERENCES cities(id) ON DELETE CASCADE,
                confirm_6h_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                confirm_3h_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                confirm_2h_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                intro_remind_3h_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                quiet_hours_start INTEGER NOT NULL DEFAULT 22,
                quiet_hours_end INTEGER NOT NULL DEFAULT 8,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_city_reminder_policies_city_id "
        "ON city_reminder_policies(city_id)"
    ))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    conn.execute(sa.text("DROP TABLE IF EXISTS city_reminder_policies"))
