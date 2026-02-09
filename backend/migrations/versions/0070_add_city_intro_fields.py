"""Add intro_address, contact_name, contact_phone to cities."""

from __future__ import annotations

import sqlalchemy as sa
from backend.migrations.utils import column_exists

revision = "0070_add_city_intro_fields"
down_revision = "0069_drop_legacy_templates"


def upgrade(conn):
    if not column_exists(conn, "cities", "intro_address"):
        conn.execute(sa.text("ALTER TABLE cities ADD COLUMN intro_address VARCHAR(255)"))
    if not column_exists(conn, "cities", "contact_name"):
        conn.execute(sa.text("ALTER TABLE cities ADD COLUMN contact_name VARCHAR(120)"))
    if not column_exists(conn, "cities", "contact_phone"):
        conn.execute(sa.text("ALTER TABLE cities ADD COLUMN contact_phone VARCHAR(50)"))


def downgrade(conn):
    if column_exists(conn, "cities", "intro_address"):
        conn.execute(sa.text("ALTER TABLE cities DROP COLUMN intro_address"))
    if column_exists(conn, "cities", "contact_name"):
        conn.execute(sa.text("ALTER TABLE cities DROP COLUMN contact_name"))
    if column_exists(conn, "cities", "contact_phone"):
        conn.execute(sa.text("ALTER TABLE cities DROP COLUMN contact_phone"))
