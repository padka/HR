"""Add manual_slot_audit_logs table for audit trail."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, index_exists


revision = "0027_add_manual_slot_audit_log"
down_revision = "0026_add_recruiter_candidate_confirmed_template"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    """Create manual_slot_audit_logs table."""

    if table_exists(conn, "manual_slot_audit_logs"):
        return

    conn.execute(sa.text("""
        CREATE TABLE manual_slot_audit_logs (
            id SERIAL PRIMARY KEY,
            slot_id INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
            candidate_tg_id BIGINT NOT NULL,
            recruiter_id INTEGER NOT NULL REFERENCES recruiters(id) ON DELETE CASCADE,
            city_id INTEGER REFERENCES cities(id) ON DELETE SET NULL,
            slot_datetime_utc TIMESTAMP WITH TIME ZONE NOT NULL,
            slot_tz VARCHAR(64) NOT NULL,
            purpose VARCHAR(32) NOT NULL DEFAULT 'interview',
            custom_message_sent BOOLEAN NOT NULL DEFAULT FALSE,
            custom_message_text TEXT,
            admin_username VARCHAR(100) NOT NULL,
            ip_address VARCHAR(45),
            user_agent VARCHAR(255),
            candidate_previous_status VARCHAR(50),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # Создаём индексы для эффективного поиска
    if not index_exists(conn, "manual_slot_audit_logs", "ix_manual_slot_audit_logs_slot_id"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS ix_manual_slot_audit_logs_slot_id
                ON manual_slot_audit_logs (slot_id)
        """))

    if not index_exists(conn, "manual_slot_audit_logs", "ix_manual_slot_audit_logs_candidate_tg_id"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS ix_manual_slot_audit_logs_candidate_tg_id
                ON manual_slot_audit_logs (candidate_tg_id)
        """))

    if not index_exists(conn, "manual_slot_audit_logs", "ix_manual_slot_audit_logs_created_at"):
        conn.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS ix_manual_slot_audit_logs_created_at
                ON manual_slot_audit_logs (created_at)
        """))


def downgrade(conn: Connection) -> None:  # pragma: no cover
    """Drop manual_slot_audit_logs table."""
    conn.execute(sa.text("DROP TABLE IF EXISTS manual_slot_audit_logs CASCADE"))
