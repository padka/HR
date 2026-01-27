"""Add internal staff messenger tables (threads, messages, attachments)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy import inspect

revision = "0060_add_staff_messenger"
down_revision = "0059_add_recruiter_plan_entries"
branch_labels = None
depends_on = None


def _table_exists(conn: Connection, table: str) -> bool:
    inspector = inspect(conn)
    try:
        return table in inspector.get_table_names()
    except Exception:
        return False


def upgrade(conn: Connection) -> None:
    if _table_exists(conn, "staff_threads"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                """
                CREATE TABLE staff_threads (
                    id INTEGER PRIMARY KEY,
                    thread_type TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE staff_thread_members (
                    thread_id INTEGER NOT NULL REFERENCES staff_threads(id) ON DELETE CASCADE,
                    principal_type TEXT NOT NULL,
                    principal_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    joined_at TIMESTAMP,
                    last_read_at TIMESTAMP,
                    PRIMARY KEY (thread_id, principal_type, principal_id)
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE staff_messages (
                    id INTEGER PRIMARY KEY,
                    thread_id INTEGER NOT NULL REFERENCES staff_threads(id) ON DELETE CASCADE,
                    sender_type TEXT NOT NULL,
                    sender_id INTEGER NOT NULL,
                    text TEXT,
                    created_at TIMESTAMP,
                    edited_at TIMESTAMP,
                    deleted_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE staff_message_attachments (
                    id INTEGER PRIMARY KEY,
                    message_id INTEGER NOT NULL REFERENCES staff_messages(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    mime_type TEXT,
                    size INTEGER,
                    storage_path TEXT NOT NULL,
                    created_at TIMESTAMP
                )
                """
            )
        )
    else:
        conn.execute(
            sa.text(
                """
                CREATE TABLE staff_threads (
                    id SERIAL PRIMARY KEY,
                    thread_type VARCHAR(16) NOT NULL,
                    title VARCHAR(180),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE staff_thread_members (
                    thread_id INTEGER NOT NULL REFERENCES staff_threads(id) ON DELETE CASCADE,
                    principal_type VARCHAR(16) NOT NULL,
                    principal_id INTEGER NOT NULL,
                    role VARCHAR(16) NOT NULL,
                    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_read_at TIMESTAMP WITH TIME ZONE,
                    PRIMARY KEY (thread_id, principal_type, principal_id)
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE staff_messages (
                    id SERIAL PRIMARY KEY,
                    thread_id INTEGER NOT NULL REFERENCES staff_threads(id) ON DELETE CASCADE,
                    sender_type VARCHAR(16) NOT NULL,
                    sender_id INTEGER NOT NULL,
                    text TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    edited_at TIMESTAMP WITH TIME ZONE,
                    deleted_at TIMESTAMP WITH TIME ZONE
                )
                """
            )
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE staff_message_attachments (
                    id SERIAL PRIMARY KEY,
                    message_id INTEGER NOT NULL REFERENCES staff_messages(id) ON DELETE CASCADE,
                    filename VARCHAR(255) NOT NULL,
                    mime_type VARCHAR(120),
                    size INTEGER,
                    storage_path VARCHAR(400) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )
        )

    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_staff_thread_members_principal "
            "ON staff_thread_members (principal_type, principal_id)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_staff_messages_thread_created_at "
            "ON staff_messages (thread_id, created_at)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_staff_message_attachments_message "
            "ON staff_message_attachments (message_id)"
        )
    )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    conn.execute(sa.text("DROP TABLE IF EXISTS staff_message_attachments"))
    conn.execute(sa.text("DROP TABLE IF EXISTS staff_messages"))
    conn.execute(sa.text("DROP TABLE IF EXISTS staff_thread_members"))
    conn.execute(sa.text("DROP TABLE IF EXISTS staff_threads"))
