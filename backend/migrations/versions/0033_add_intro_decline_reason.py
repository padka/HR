"""Add intro decline reason field to users.

Revision ID: 0033_add_intro_decline_reason
Revises: 0032_add_conversation_mode
Create Date: 2025-11-27
"""

from __future__ import annotations

from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "0033_add_intro_decline_reason"
down_revision = "0032_add_conversation_mode"
branch_labels = None
depends_on = None


def upgrade(conn):
    conn.execute(text("ALTER TABLE users ADD COLUMN intro_decline_reason TEXT"))


def downgrade(conn):
    # SQLite cannot drop columns easily; noop for downgrade.
    pass
