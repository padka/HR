"""Add slot assignment flow tables and slot capacity."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import table_exists, column_exists, index_exists

revision = "0062_slot_assignments"
down_revision = "0061_staff_message_tasks"
branch_labels = None
depends_on = None


def upgrade(conn: Connection) -> None:
    if table_exists(conn, "slots") and not column_exists(conn, "slots", "capacity"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    "ALTER TABLE slots ADD COLUMN capacity INTEGER NOT NULL DEFAULT 1"
                )
            )
        else:
            conn.execute(
                sa.text(
                    "ALTER TABLE slots ADD COLUMN capacity INTEGER NOT NULL DEFAULT 1"
                )
            )

    if not table_exists(conn, "slot_assignments"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE slot_assignments (
                        id INTEGER PRIMARY KEY,
                        slot_id INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
                        recruiter_id INTEGER NOT NULL REFERENCES recruiters(id) ON DELETE CASCADE,
                        candidate_id TEXT REFERENCES users(candidate_id) ON DELETE SET NULL,
                        candidate_tg_id BIGINT,
                        candidate_tz TEXT,
                        status TEXT NOT NULL,
                        status_before_reschedule TEXT,
                        offered_at TIMESTAMP,
                        confirmed_at TIMESTAMP,
                        reschedule_requested_at TIMESTAMP,
                        cancelled_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE slot_assignments (
                        id SERIAL PRIMARY KEY,
                        slot_id INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
                        recruiter_id INTEGER NOT NULL REFERENCES recruiters(id) ON DELETE CASCADE,
                        candidate_id VARCHAR(36) REFERENCES users(candidate_id) ON DELETE SET NULL,
                        candidate_tg_id BIGINT,
                        candidate_tz VARCHAR(64),
                        status VARCHAR(32) NOT NULL,
                        status_before_reschedule VARCHAR(32),
                        offered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        confirmed_at TIMESTAMP WITH TIME ZONE,
                        reschedule_requested_at TIMESTAMP WITH TIME ZONE,
                        cancelled_at TIMESTAMP WITH TIME ZONE,
                        completed_at TIMESTAMP WITH TIME ZONE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
            )

    if not table_exists(conn, "slot_reschedule_requests"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE slot_reschedule_requests (
                        id INTEGER PRIMARY KEY,
                        slot_assignment_id INTEGER NOT NULL REFERENCES slot_assignments(id) ON DELETE CASCADE,
                        requested_start_utc TIMESTAMP NOT NULL,
                        requested_tz TEXT,
                        candidate_comment TEXT,
                        status TEXT NOT NULL,
                        decided_at TIMESTAMP,
                        decided_by_type TEXT,
                        decided_by_id INTEGER,
                        recruiter_comment TEXT,
                        alternative_slot_id INTEGER REFERENCES slots(id) ON DELETE SET NULL,
                        created_at TIMESTAMP
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE slot_reschedule_requests (
                        id SERIAL PRIMARY KEY,
                        slot_assignment_id INTEGER NOT NULL REFERENCES slot_assignments(id) ON DELETE CASCADE,
                        requested_start_utc TIMESTAMP WITH TIME ZONE NOT NULL,
                        requested_tz VARCHAR(64),
                        candidate_comment TEXT,
                        status VARCHAR(16) NOT NULL,
                        decided_at TIMESTAMP WITH TIME ZONE,
                        decided_by_type VARCHAR(16),
                        decided_by_id INTEGER,
                        recruiter_comment TEXT,
                        alternative_slot_id INTEGER REFERENCES slots(id) ON DELETE SET NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
            )

    if not table_exists(conn, "action_tokens"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE action_tokens (
                        token TEXT PRIMARY KEY,
                        action TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        used_at TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE action_tokens (
                        token VARCHAR(64) PRIMARY KEY,
                        action VARCHAR(64) NOT NULL,
                        entity_id VARCHAR(64) NOT NULL,
                        used_at TIMESTAMP WITH TIME ZONE,
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
            )

    if not table_exists(conn, "message_logs"):
        if conn.dialect.name == "sqlite":
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE message_logs (
                        id INTEGER PRIMARY KEY,
                        channel TEXT NOT NULL,
                        recipient_type TEXT NOT NULL,
                        recipient_id BIGINT,
                        slot_assignment_id INTEGER REFERENCES slot_assignments(id) ON DELETE SET NULL,
                        message_type TEXT NOT NULL,
                        payload_json TEXT,
                        status TEXT NOT NULL,
                        created_at TIMESTAMP
                    )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE message_logs (
                        id SERIAL PRIMARY KEY,
                        channel VARCHAR(16) NOT NULL,
                        recipient_type VARCHAR(16) NOT NULL,
                        recipient_id BIGINT,
                        slot_assignment_id INTEGER REFERENCES slot_assignments(id) ON DELETE SET NULL,
                        message_type VARCHAR(64) NOT NULL,
                        payload_json JSON,
                        status VARCHAR(20) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
            )

    if table_exists(conn, "slot_assignments") and not index_exists(
        conn, "slot_assignments", "ix_slot_assignments_slot_status"
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_slot_assignments_slot_status "
                "ON slot_assignments (slot_id, status)"
            )
        )

    if table_exists(conn, "slot_assignments") and not index_exists(
        conn, "slot_assignments", "ix_slot_assignments_candidate_status"
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_slot_assignments_candidate_status "
                "ON slot_assignments (candidate_id, status)"
            )
        )

    if table_exists(conn, "slot_assignments") and not index_exists(
        conn, "slot_assignments", "ix_slot_assignments_recruiter_status"
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_slot_assignments_recruiter_status "
                "ON slot_assignments (recruiter_id, status)"
            )
        )

    if conn.dialect.name != "sqlite" and table_exists(conn, "slot_assignments"):
        conn.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_slot_assignments_candidate_active
                ON slot_assignments (candidate_id)
                WHERE status IN ('offered', 'confirmed', 'reschedule_requested', 'reschedule_confirmed')
                """
            )
        )

    if table_exists(conn, "slot_reschedule_requests") and not index_exists(
        conn, "slot_reschedule_requests", "ix_slot_reschedule_assignment_status"
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_slot_reschedule_assignment_status "
                "ON slot_reschedule_requests (slot_assignment_id, status)"
            )
        )

    if conn.dialect.name != "sqlite" and table_exists(conn, "slot_reschedule_requests"):
        conn.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_slot_reschedule_pending
                ON slot_reschedule_requests (slot_assignment_id)
                WHERE status = 'pending'
                """
            )
        )

    if table_exists(conn, "action_tokens") and not index_exists(
        conn, "action_tokens", "ix_action_tokens_action_entity"
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_action_tokens_action_entity "
                "ON action_tokens (action, entity_id)"
            )
        )

    if table_exists(conn, "message_logs") and not index_exists(
        conn, "message_logs", "ix_message_logs_assignment"
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_message_logs_assignment "
                "ON message_logs (slot_assignment_id)"
            )
        )

    if table_exists(conn, "message_logs") and not index_exists(
        conn, "message_logs", "ix_message_logs_recipient"
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_message_logs_recipient "
                "ON message_logs (recipient_type, recipient_id)"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    if table_exists(conn, "message_logs"):
        conn.execute(sa.text("DROP TABLE IF EXISTS message_logs"))
    if table_exists(conn, "action_tokens"):
        conn.execute(sa.text("DROP TABLE IF EXISTS action_tokens"))
    if table_exists(conn, "slot_reschedule_requests"):
        conn.execute(sa.text("DROP TABLE IF EXISTS slot_reschedule_requests"))
    if table_exists(conn, "slot_assignments"):
        conn.execute(sa.text("DROP TABLE IF EXISTS slot_assignments"))
    if column_exists(conn, "slots", "capacity"):
        if conn.dialect.name != "sqlite":
            conn.execute(sa.text("ALTER TABLE slots DROP COLUMN capacity"))
