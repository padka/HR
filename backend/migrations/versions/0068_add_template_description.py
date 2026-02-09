"""Add description to message_templates."""

from __future__ import annotations

import sqlalchemy as sa
from backend.migrations.utils import column_exists

revision = "0068_add_template_description"
down_revision = "0067_add_fk_indexes"


def upgrade(conn):
    if not column_exists(conn, "message_templates", "description"):
        conn.execute(sa.text("ALTER TABLE message_templates ADD COLUMN description VARCHAR(255)"))
    
    if not column_exists(conn, "message_template_history", "description"):
        conn.execute(sa.text("ALTER TABLE message_template_history ADD COLUMN description VARCHAR(255)"))


def downgrade(conn):
    if column_exists(conn, "message_templates", "description"):
        conn.execute(sa.text("ALTER TABLE message_templates DROP COLUMN description"))
    
    if column_exists(conn, "message_template_history", "description"):
        conn.execute(sa.text("ALTER TABLE message_template_history DROP COLUMN description"))
