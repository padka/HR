"""Add intro_day_template to City."""

from __future__ import annotations

import sqlalchemy as sa

revision = "0065_add_intro_day_template_to_city"
down_revision = "0064_add_test_questions_tables"


def upgrade(conn):
    conn.execute(sa.text("ALTER TABLE cities ADD COLUMN intro_day_template TEXT"))


def downgrade(conn):
    conn.execute(sa.text("ALTER TABLE cities DROP COLUMN intro_day_template"))
