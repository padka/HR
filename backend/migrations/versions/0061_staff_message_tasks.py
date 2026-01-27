"""Add staff message tasks and message types."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, column_exists, index_exists

revision = "0061_staff_message_tasks"
down_revision = "0060_add_staff_messenger"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if table_exists(conn, "staff_messages") and not column_exists(conn, "staff_messages", "message_type"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text("ALTER TABLE staff_messages ADD COLUMN message_type TEXT NOT NULL DEFAULT 'text'")
            )
        else:
            conn.execute(
                sa.text("ALTER TABLE staff_messages ADD COLUMN message_type VARCHAR(24) NOT NULL DEFAULT 'text'")
            )
        conn.execute(sa.text("UPDATE staff_messages SET message_type = 'text' WHERE message_type IS NULL"))

    if not table_exists(conn, "staff_message_tasks"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE staff_message_tasks (
                        message_id INTEGER PRIMARY KEY REFERENCES staff_messages(id) ON DELETE CASCADE,
                        candidate_id INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        created_at TIMESTAMP,
                        decided_at TIMESTAMP,
                        decided_by_type TEXT,
                        decided_by_id INTEGER,
                        decision_comment TEXT
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE staff_message_tasks (
                        message_id INTEGER PRIMARY KEY REFERENCES staff_messages(id) ON DELETE CASCADE,
                        candidate_id INTEGER NOT NULL,
                        status VARCHAR(16) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        decided_at TIMESTAMP WITH TIME ZONE,
                        decided_by_type VARCHAR(16),
                        decided_by_id INTEGER,
                        decision_comment TEXT
                    )
                    """
                )
            )

    if table_exists(conn, "staff_message_tasks") and not index_exists(
        conn, "staff_message_tasks", "ix_staff_message_tasks_candidate"
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_staff_message_tasks_candidate "
                "ON staff_message_tasks (candidate_id)"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    if table_exists(conn, "staff_message_tasks"):
        conn.execute(sa.text("DROP TABLE IF EXISTS staff_message_tasks"))

    if column_exists(conn, "staff_messages", "message_type"):
        if conn.dialect.name != "sqlite":
            conn.execute(sa.text("ALTER TABLE staff_messages DROP COLUMN message_type"))
