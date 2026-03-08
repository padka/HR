"""Support free-form reschedule requests and candidate chat read states."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists, table_exists

revision = "0093_reschedule_windows_and_candidate_chat_reads"
down_revision = "0092_allow_unbound_hh_vacancy_bindings"
branch_labels = None
depends_on = None


def _column_nullable(conn: Connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(conn)
    for column in inspector.get_columns(table_name):
        if column.get("name") == column_name:
            return bool(column.get("nullable", True))
    return True


def _ensure_reschedule_indexes(conn: Connection) -> None:
    if not index_exists(
        conn,
        "slot_reschedule_requests",
        "ix_slot_reschedule_assignment_status",
    ):
        conn.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS ix_slot_reschedule_assignment_status
                ON slot_reschedule_requests (slot_assignment_id, status)
                """
            )
        )
    if not index_exists(conn, "slot_reschedule_requests", "uq_slot_reschedule_pending"):
        conn.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_slot_reschedule_pending
                ON slot_reschedule_requests (slot_assignment_id)
                WHERE status = 'pending'
                """
            )
        )


def _rebuild_reschedule_requests_sqlite(conn: Connection, *, downgrade: bool = False) -> None:
    inspector = sa.inspect(conn)
    old_columns = {column.get("name") for column in inspector.get_columns("slot_reschedule_requests")}
    has_requested_end = "requested_end_utc" in old_columns

    insert_requested_end = "requested_end_utc" if has_requested_end and not downgrade else "NULL AS requested_end_utc"

    conn.execute(sa.text("PRAGMA foreign_keys=OFF"))
    try:
        conn.execute(sa.text("ALTER TABLE slot_reschedule_requests RENAME TO slot_reschedule_requests_old"))
        if downgrade:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE slot_reschedule_requests (
                        id INTEGER PRIMARY KEY,
                        slot_assignment_id INTEGER NOT NULL REFERENCES slot_assignments(id) ON DELETE CASCADE,
                        requested_start_utc TIMESTAMP NOT NULL,
                        requested_tz VARCHAR(64),
                        candidate_comment TEXT,
                        status VARCHAR(16) NOT NULL,
                        decided_at TIMESTAMP,
                        decided_by_type VARCHAR(16),
                        decided_by_id INTEGER,
                        recruiter_comment TEXT,
                        alternative_slot_id INTEGER REFERENCES slots(id) ON DELETE SET NULL,
                        created_at TIMESTAMP NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                sa.text(
                    """
                    INSERT INTO slot_reschedule_requests (
                        id,
                        slot_assignment_id,
                        requested_start_utc,
                        requested_tz,
                        candidate_comment,
                        status,
                        decided_at,
                        decided_by_type,
                        decided_by_id,
                        recruiter_comment,
                        alternative_slot_id,
                        created_at
                    )
                    SELECT
                        id,
                        slot_assignment_id,
                        requested_start_utc,
                        requested_tz,
                        candidate_comment,
                        status,
                        decided_at,
                        decided_by_type,
                        decided_by_id,
                        recruiter_comment,
                        alternative_slot_id,
                        created_at
                    FROM slot_reschedule_requests_old
                    WHERE requested_start_utc IS NOT NULL
                      AND (
                        requested_end_utc IS NULL
                        OR requested_end_utc = requested_start_utc
                      )
                    """
                )
            )
        else:
            conn.execute(
                sa.text(
                    """
                    CREATE TABLE slot_reschedule_requests (
                        id INTEGER PRIMARY KEY,
                        slot_assignment_id INTEGER NOT NULL REFERENCES slot_assignments(id) ON DELETE CASCADE,
                        requested_start_utc TIMESTAMP,
                        requested_end_utc TIMESTAMP,
                        requested_tz VARCHAR(64),
                        candidate_comment TEXT,
                        status VARCHAR(16) NOT NULL,
                        decided_at TIMESTAMP,
                        decided_by_type VARCHAR(16),
                        decided_by_id INTEGER,
                        recruiter_comment TEXT,
                        alternative_slot_id INTEGER REFERENCES slots(id) ON DELETE SET NULL,
                        created_at TIMESTAMP NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                sa.text(
                    f"""
                    INSERT INTO slot_reschedule_requests (
                        id,
                        slot_assignment_id,
                        requested_start_utc,
                        requested_end_utc,
                        requested_tz,
                        candidate_comment,
                        status,
                        decided_at,
                        decided_by_type,
                        decided_by_id,
                        recruiter_comment,
                        alternative_slot_id,
                        created_at
                    )
                    SELECT
                        id,
                        slot_assignment_id,
                        requested_start_utc,
                        {insert_requested_end},
                        requested_tz,
                        candidate_comment,
                        status,
                        decided_at,
                        decided_by_type,
                        decided_by_id,
                        recruiter_comment,
                        alternative_slot_id,
                        created_at
                    FROM slot_reschedule_requests_old
                    """
                )
            )
        conn.execute(sa.text("DROP TABLE slot_reschedule_requests_old"))
    finally:
        conn.execute(sa.text("PRAGMA foreign_keys=ON"))


def _upgrade_reschedule_requests(conn: Connection) -> None:
    if not table_exists(conn, "slot_reschedule_requests"):
        return

    if conn.dialect.name == "sqlite":
        if (
            not column_exists(conn, "slot_reschedule_requests", "requested_end_utc")
            or not _column_nullable(conn, "slot_reschedule_requests", "requested_start_utc")
        ):
            _rebuild_reschedule_requests_sqlite(conn)
    else:
        if not column_exists(conn, "slot_reschedule_requests", "requested_end_utc"):
            conn.execute(
                sa.text(
                    "ALTER TABLE slot_reschedule_requests "
                    "ADD COLUMN requested_end_utc TIMESTAMP WITH TIME ZONE"
                )
            )
        conn.execute(
            sa.text(
                "ALTER TABLE slot_reschedule_requests "
                "ALTER COLUMN requested_start_utc DROP NOT NULL"
            )
        )
    _ensure_reschedule_indexes(conn)


def _create_candidate_chat_reads(conn: Connection) -> None:
    if table_exists(conn, "candidate_chat_reads"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                """
                CREATE TABLE candidate_chat_reads (
                    id INTEGER PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    principal_type TEXT NOT NULL,
                    principal_id INTEGER NOT NULL,
                    last_read_at TIMESTAMP,
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
                CREATE TABLE candidate_chat_reads (
                    id SERIAL PRIMARY KEY,
                    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    principal_type VARCHAR(16) NOT NULL,
                    principal_id INTEGER NOT NULL,
                    last_read_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )
        )

    if not index_exists(
        conn,
        "candidate_chat_reads",
        "ix_candidate_chat_reads_principal",
    ):
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_candidate_chat_reads_principal "
                "ON candidate_chat_reads (principal_type, principal_id, last_read_at)"
            )
        )

    if not index_exists(
        conn,
        "candidate_chat_reads",
        "uq_candidate_chat_reads_principal",
    ):
        conn.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_chat_reads_principal
                ON candidate_chat_reads (candidate_id, principal_type, principal_id)
                """
            )
        )


def upgrade(conn: Connection) -> None:
    _upgrade_reschedule_requests(conn)
    _create_candidate_chat_reads(conn)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if table_exists(conn, "candidate_chat_reads"):
        conn.execute(sa.text("DROP TABLE candidate_chat_reads"))

    if not table_exists(conn, "slot_reschedule_requests"):
        return

    if conn.dialect.name == "sqlite":
        _rebuild_reschedule_requests_sqlite(conn, downgrade=True)
        _ensure_reschedule_indexes(conn)
        return

    conn.execute(
        sa.text(
            "DELETE FROM slot_reschedule_requests "
            "WHERE requested_start_utc IS NULL OR requested_end_utc IS NOT NULL"
        )
    )
    conn.execute(
        sa.text(
            "ALTER TABLE slot_reschedule_requests "
            "DROP COLUMN IF EXISTS requested_end_utc"
        )
    )
    conn.execute(
        sa.text(
            "ALTER TABLE slot_reschedule_requests "
            "ALTER COLUMN requested_start_utc SET NOT NULL"
        )
    )
