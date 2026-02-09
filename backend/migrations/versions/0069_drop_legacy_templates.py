"""Drop legacy templates table and city column."""

from __future__ import annotations

import sqlalchemy as sa
from backend.migrations.utils import table_exists, column_exists

revision = "0069_drop_legacy_templates"
down_revision = "0068_add_template_description"


def upgrade(conn):
    if table_exists(conn, "templates"):
        conn.execute(sa.text("DROP TABLE templates CASCADE"))
    
    if column_exists(conn, "cities", "intro_day_template"):
        conn.execute(sa.text("ALTER TABLE cities DROP COLUMN intro_day_template"))


def downgrade(conn):
    if not table_exists(conn, "templates"):
        conn.execute(sa.text("""
            CREATE TABLE templates (
                id SERIAL PRIMARY KEY,
                city_id INTEGER,
                key VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                CONSTRAINT uq_city_key UNIQUE (city_id, key),
                CONSTRAINT fk_templates_city_id FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE
            )
        """))
    
    if not column_exists(conn, "cities", "intro_day_template"):
        conn.execute(sa.text("ALTER TABLE cities ADD COLUMN intro_day_template TEXT"))
