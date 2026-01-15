"""Add UUID candidate identity, source fields, and slot candidate linkage."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import column_exists, index_exists, table_exists

revision = "0043_add_candidate_uuid_and_lead_source"
down_revision = "0042_add_comprehensive_slot_indexes"
branch_labels = None
depends_on = None


def _backfill_candidate_ids(conn: Connection) -> None:
    rows = conn.execute(sa.text("SELECT id FROM users WHERE candidate_id IS NULL")).fetchall()
    for (user_id,) in rows:
        conn.execute(
            sa.text("UPDATE users SET candidate_id = :candidate_id WHERE id = :user_id"),
            {"candidate_id": str(uuid.uuid4()), "user_id": user_id},
        )


def _upgrade_users_sqlite(conn: Connection) -> None:
    if not table_exists(conn, "users"):
        return

    conn.execute(sa.text("PRAGMA foreign_keys=OFF"))
    conn.execute(sa.text("ALTER TABLE users RENAME TO users_old"))

    conn.execute(
        sa.text(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                candidate_id VARCHAR(36) NOT NULL UNIQUE,
                telegram_id BIGINT UNIQUE,
                username VARCHAR(32),
                telegram_user_id BIGINT,
                telegram_username VARCHAR(64),
                telegram_linked_at TIMESTAMP,
                conversation_mode VARCHAR(16) NOT NULL DEFAULT 'flow',
                conversation_mode_expires_at TIMESTAMP,
                fio VARCHAR(160) NOT NULL,
                city VARCHAR(120),
                desired_position VARCHAR(120),
                resume_filename VARCHAR(255),
                test1_report_url VARCHAR(255),
                test2_report_url VARCHAR(255),
                is_active BOOLEAN NOT NULL DEFAULT 1,
                candidate_status VARCHAR(50),
                status_changed_at TIMESTAMP,
                last_activity TIMESTAMP NOT NULL,
                manual_slot_from TIMESTAMP,
                manual_slot_to TIMESTAMP,
                manual_slot_comment TEXT,
                manual_slot_timezone VARCHAR(64),
                manual_slot_requested_at TIMESTAMP,
                manual_slot_response_at TIMESTAMP,
                intro_decline_reason TEXT,
                source VARCHAR(32) NOT NULL DEFAULT 'bot',
                phone VARCHAR(32),
                assigned_recruiter_id INTEGER,
                FOREIGN KEY (assigned_recruiter_id) REFERENCES recruiters(id) ON DELETE SET NULL
            )
            """
        )
    )

    rows = conn.execute(sa.text("SELECT * FROM users_old")).fetchall()
    now = datetime.now(timezone.utc)

    insert_stmt = sa.text(
        """
        INSERT INTO users (
            id,
            candidate_id,
            telegram_id,
            username,
            telegram_user_id,
            telegram_username,
            telegram_linked_at,
            conversation_mode,
            conversation_mode_expires_at,
            fio,
            city,
            desired_position,
            resume_filename,
            test1_report_url,
            test2_report_url,
            is_active,
            candidate_status,
            status_changed_at,
            last_activity,
            manual_slot_from,
            manual_slot_to,
            manual_slot_comment,
            manual_slot_timezone,
            manual_slot_requested_at,
            manual_slot_response_at,
            intro_decline_reason,
            source,
            phone,
            assigned_recruiter_id
        ) VALUES (
            :id,
            :candidate_id,
            :telegram_id,
            :username,
            :telegram_user_id,
            :telegram_username,
            :telegram_linked_at,
            :conversation_mode,
            :conversation_mode_expires_at,
            :fio,
            :city,
            :desired_position,
            :resume_filename,
            :test1_report_url,
            :test2_report_url,
            :is_active,
            :candidate_status,
            :status_changed_at,
            :last_activity,
            :manual_slot_from,
            :manual_slot_to,
            :manual_slot_comment,
            :manual_slot_timezone,
            :manual_slot_requested_at,
            :manual_slot_response_at,
            :intro_decline_reason,
            :source,
            :phone,
            :assigned_recruiter_id
        )
        """
    )

    for row in rows:
        data = row._mapping
        payload = {
            "id": data.get("id"),
            "candidate_id": data.get("candidate_id") or str(uuid.uuid4()),
            "telegram_id": data.get("telegram_id"),
            "username": data.get("username"),
            "telegram_user_id": data.get("telegram_user_id"),
            "telegram_username": data.get("telegram_username"),
            "telegram_linked_at": data.get("telegram_linked_at"),
            "conversation_mode": data.get("conversation_mode") or "flow",
            "conversation_mode_expires_at": data.get("conversation_mode_expires_at"),
            "fio": data.get("fio"),
            "city": data.get("city"),
            "desired_position": data.get("desired_position"),
            "resume_filename": data.get("resume_filename"),
            "test1_report_url": data.get("test1_report_url"),
            "test2_report_url": data.get("test2_report_url"),
            "is_active": data.get("is_active", 1),
            "candidate_status": data.get("candidate_status"),
            "status_changed_at": data.get("status_changed_at"),
            "last_activity": data.get("last_activity") or now,
            "manual_slot_from": data.get("manual_slot_from"),
            "manual_slot_to": data.get("manual_slot_to"),
            "manual_slot_comment": data.get("manual_slot_comment"),
            "manual_slot_timezone": data.get("manual_slot_timezone"),
            "manual_slot_requested_at": data.get("manual_slot_requested_at"),
            "manual_slot_response_at": data.get("manual_slot_response_at"),
            "intro_decline_reason": data.get("intro_decline_reason"),
            "source": data.get("source") or "bot",
            "phone": data.get("phone"),
            "assigned_recruiter_id": data.get("assigned_recruiter_id"),
        }
        conn.execute(insert_stmt, payload)

    conn.execute(sa.text("DROP TABLE users_old"))

    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_telegram_id ON users (telegram_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)"))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_telegram_user_id ON users (telegram_user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_candidate_status ON users (candidate_status)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_assigned_recruiter_id ON users (assigned_recruiter_id)"))
    conn.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_candidate_id ON users (candidate_id)"))

    conn.execute(sa.text("PRAGMA foreign_keys=ON"))


def _upgrade_users(conn: Connection) -> None:
    if not table_exists(conn, "users"):
        return

    if conn.dialect.name == "sqlite":
        _upgrade_users_sqlite(conn)
        return

    if not column_exists(conn, "users", "candidate_id"):
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN candidate_id VARCHAR(36)"))
    _backfill_candidate_ids(conn)
    conn.execute(sa.text("ALTER TABLE users ALTER COLUMN candidate_id SET NOT NULL"))
    if not index_exists(conn, "users", "ix_users_candidate_id"):
        conn.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_candidate_id ON users (candidate_id)"
            )
        )

    if not column_exists(conn, "users", "source"):
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN source VARCHAR(32)"))
    conn.execute(sa.text("UPDATE users SET source = 'bot' WHERE source IS NULL"))
    conn.execute(sa.text("ALTER TABLE users ALTER COLUMN source SET NOT NULL"))

    if not column_exists(conn, "users", "phone"):
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN phone VARCHAR(32)"))

    if column_exists(conn, "users", "telegram_id"):
        conn.execute(sa.text("ALTER TABLE users ALTER COLUMN telegram_id DROP NOT NULL"))


def _upgrade_slots(conn: Connection) -> None:
    if not table_exists(conn, "slots"):
        return

    if not column_exists(conn, "slots", "candidate_id"):
        conn.execute(sa.text("ALTER TABLE slots ADD COLUMN candidate_id VARCHAR(36)"))

    conn.execute(
        sa.text(
            """
            UPDATE slots
            SET candidate_id = (
                SELECT candidate_id FROM users WHERE users.telegram_id = slots.candidate_tg_id
            )
            WHERE candidate_id IS NULL AND candidate_tg_id IS NOT NULL
            """
        )
    )

    if not index_exists(conn, "slots", "ix_slots_candidate_id_start"):
        conn.execute(
            sa.text(
                """
                CREATE INDEX IF NOT EXISTS ix_slots_candidate_id_start
                ON slots (candidate_id, start_utc DESC)
                WHERE candidate_id IS NOT NULL
                """
            )
        )


def _upgrade_slot_reservation_locks(conn: Connection) -> None:
    if not table_exists(conn, "slot_reservation_locks"):
        return

    if conn.dialect.name == "sqlite":
        conn.execute(sa.text("PRAGMA foreign_keys=OFF"))
        conn.execute(sa.text("ALTER TABLE slot_reservation_locks RENAME TO slot_reservation_locks_old"))
        conn.execute(
            sa.text(
                """
                CREATE TABLE slot_reservation_locks (
                    id INTEGER PRIMARY KEY,
                    slot_id INTEGER NOT NULL,
                    candidate_id VARCHAR(36),
                    candidate_tg_id BIGINT,
                    recruiter_id INTEGER NOT NULL,
                    reservation_date DATE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        rows = conn.execute(sa.text("SELECT * FROM slot_reservation_locks_old")).fetchall()
        insert_stmt = sa.text(
            """
            INSERT INTO slot_reservation_locks (
                id, slot_id, candidate_id, candidate_tg_id, recruiter_id, reservation_date, expires_at, created_at
            ) VALUES (
                :id, :slot_id, :candidate_id, :candidate_tg_id, :recruiter_id, :reservation_date, :expires_at, :created_at
            )
            """
        )
        for row in rows:
            data = row._mapping
            conn.execute(
                insert_stmt,
                {
                    "id": data.get("id"),
                    "slot_id": data.get("slot_id"),
                    "candidate_id": data.get("candidate_id"),
                    "candidate_tg_id": data.get("candidate_tg_id"),
                    "recruiter_id": data.get("recruiter_id"),
                    "reservation_date": data.get("reservation_date"),
                    "expires_at": data.get("expires_at"),
                    "created_at": data.get("created_at"),
                },
            )
        conn.execute(sa.text("DROP TABLE slot_reservation_locks_old"))
        conn.execute(
            sa.text(
                """
                UPDATE slot_reservation_locks
                SET candidate_id = (
                    SELECT candidate_id FROM users WHERE users.telegram_id = slot_reservation_locks.candidate_tg_id
                )
                WHERE candidate_id IS NULL AND candidate_tg_id IS NOT NULL
                """
            )
        )
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_slot_reservation_locks_candidate_id "
                "ON slot_reservation_locks (candidate_id)"
            )
        )
        conn.execute(sa.text("PRAGMA foreign_keys=ON"))
    else:
        if column_exists(conn, "slot_reservation_locks", "candidate_tg_id"):
            conn.execute(
                sa.text(
                    "ALTER TABLE slot_reservation_locks ALTER COLUMN candidate_tg_id DROP NOT NULL"
                )
            )
        if not column_exists(conn, "slot_reservation_locks", "candidate_id"):
            conn.execute(
                sa.text("ALTER TABLE slot_reservation_locks ADD COLUMN candidate_id VARCHAR(36)")
            )

        conn.execute(
            sa.text(
                """
                UPDATE slot_reservation_locks
                SET candidate_id = (
                    SELECT candidate_id FROM users WHERE users.telegram_id = slot_reservation_locks.candidate_tg_id
                )
                WHERE candidate_id IS NULL AND candidate_tg_id IS NOT NULL
                """
            )
        )

        if not index_exists(conn, "slot_reservation_locks", "ix_slot_reservation_locks_candidate_id"):
            conn.execute(
                sa.text(
                    "CREATE INDEX IF NOT EXISTS ix_slot_reservation_locks_candidate_id "
                    "ON slot_reservation_locks (candidate_id)"
                )
            )


def _upgrade_invite_tokens(conn: Connection) -> None:
    if table_exists(conn, "candidate_invite_tokens"):
        return

    conn.execute(
        sa.text(
            """
            CREATE TABLE candidate_invite_tokens (
                id INTEGER PRIMARY KEY,
                candidate_id VARCHAR(36) NOT NULL,
                token VARCHAR(64) NOT NULL UNIQUE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                used_at TIMESTAMP WITH TIME ZONE,
                used_by_telegram_id BIGINT,
                FOREIGN KEY (candidate_id) REFERENCES users(candidate_id) ON DELETE CASCADE
            )
            """
        )
    )

    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_candidate_invite_tokens_candidate_id "
            "ON candidate_invite_tokens (candidate_id)"
        )
    )


def upgrade(conn: Connection) -> None:
    _upgrade_users(conn)
    _upgrade_slots(conn)
    _upgrade_slot_reservation_locks(conn)
    _upgrade_invite_tokens(conn)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    if table_exists(conn, "candidate_invite_tokens"):
        conn.execute(sa.text("DROP TABLE IF EXISTS candidate_invite_tokens"))

    if table_exists(conn, "slot_reservation_locks") and column_exists(
        conn, "slot_reservation_locks", "candidate_id"
    ):
        conn.execute(sa.text("ALTER TABLE slot_reservation_locks DROP COLUMN candidate_id"))

    if table_exists(conn, "slots") and column_exists(conn, "slots", "candidate_id"):
        conn.execute(sa.text("ALTER TABLE slots DROP COLUMN candidate_id"))

    if table_exists(conn, "users"):
        if column_exists(conn, "users", "phone"):
            conn.execute(sa.text("ALTER TABLE users DROP COLUMN phone"))
        if column_exists(conn, "users", "source"):
            conn.execute(sa.text("ALTER TABLE users DROP COLUMN source"))
        if column_exists(conn, "users", "candidate_id"):
            conn.execute(sa.text("ALTER TABLE users DROP COLUMN candidate_id"))
