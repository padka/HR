"""Add generic audit_log table for admin actions."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import index_exists, table_exists


revision = "0040_add_audit_log_table"
down_revision = "0039_allow_multiple_recruiters_per_city"
branch_labels = None
depends_on = None


TABLE_NAME = "audit_log"


def upgrade(conn: Connection) -> None:
    """Create audit_log table to capture admin actions."""
    if table_exists(conn, TABLE_NAME):
        return

    conn.execute(
        sa.text(
            """
            CREATE TABLE audit_log (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                username VARCHAR(100),
                action VARCHAR(100) NOT NULL,
                entity_type VARCHAR(50),
                entity_id VARCHAR(64),
                ip_address VARCHAR(45),
                user_agent VARCHAR(255),
                changes JSONB
            )
            """
        )
    )

    for index_name, column in [
        ("ix_audit_log_created_at", "created_at"),
        ("ix_audit_log_username", "username"),
        ("ix_audit_log_action", "action"),
        ("ix_audit_log_entity_type", "entity_type"),
        ("ix_audit_log_entity_id", "entity_id"),
    ]:
        if not index_exists(conn, TABLE_NAME, index_name):
            conn.execute(
                sa.text(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {TABLE_NAME} ({column})"
                )
            )


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Drop audit_log table."""
    if not table_exists(conn, TABLE_NAME):
        return
    conn.execute(sa.text("DROP TABLE IF EXISTS audit_log CASCADE"))
