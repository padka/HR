from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

revision = "0012_update_slots_candidate_recruiter_index"
down_revision = "0011_add_candidate_binding_to_notification_logs"
branch_labels = None
depends_on = None

TABLE_NAME = "slots"
INDEX_NAME = "uq_slots_candidate_recruiter_active"
ACTIVE_STATUSES = "('pending','booked','confirmed_by_candidate')"
LEGACY_STATUSES = "('pending','booked')"


def _dialect_name(conn: Connection) -> str:
    dialect = getattr(conn, "dialect", None)
    return dialect.name if dialect is not None else ""


def _drop_index(conn: Connection, dialect_name: str) -> None:
    if dialect_name == "postgresql":
        conn.execute(text(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}"))
    else:
        conn.execute(text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))


def _create_index(conn: Connection, dialect_name: str, statuses: str) -> None:
    where_clause = f"lower(status) IN {statuses}"
    if dialect_name == "postgresql":
        conn.execute(
            text(
                f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
                f"ON {TABLE_NAME} (candidate_tg_id, recruiter_id) WHERE {where_clause}"
            )
        )
    else:
        conn.execute(
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME} "
                f"ON {TABLE_NAME} (candidate_tg_id, recruiter_id) WHERE {where_clause}"
            )
        )


def upgrade(conn: Connection) -> None:
    dialect_name = _dialect_name(conn)
    _drop_index(conn, dialect_name)
    _create_index(conn, dialect_name, ACTIVE_STATUSES)


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    dialect_name = _dialect_name(conn)
    _drop_index(conn, dialect_name)
    _create_index(conn, dialect_name, LEGACY_STATUSES)
