from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

revision = "0011_add_candidate_binding_to_notification_logs"
down_revision = "0010_add_notification_logs"
branch_labels = None
depends_on = None

TABLE_NAME = "notification_logs"
CANDIDATE_COLUMN = "candidate_tg_id"
OLD_CONSTRAINT = "uq_notification_logs_type_booking"
NEW_INDEX = "uq_notif_type_booking_candidate"


def _dialect_name(conn: Connection) -> str:
    dialect = getattr(conn, "dialect", None)
    return dialect.name if dialect is not None else ""


def upgrade(conn: Connection) -> None:
    dialect_name = _dialect_name(conn)

    conn.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {CANDIDATE_COLUMN} BIGINT"))

    if dialect_name == "sqlite":
        conn.execute(text(f"DROP INDEX IF EXISTS {OLD_CONSTRAINT}"))
    else:
        conn.execute(
            text(
                f"ALTER TABLE {TABLE_NAME} DROP CONSTRAINT IF EXISTS {OLD_CONSTRAINT}"
            )
        )

    conn.execute(
        text(
            """
            UPDATE {table}
               SET {column} = (
                   SELECT candidate_tg_id
                     FROM slots
                    WHERE slots.id = {table}.booking_id
               )
             WHERE {column} IS NULL
               AND EXISTS (
                   SELECT 1 FROM slots
                    WHERE slots.id = {table}.booking_id
                      AND slots.candidate_tg_id IS NOT NULL
               )
            """.format(table=TABLE_NAME, column=CANDIDATE_COLUMN)
        )
    )

    if dialect_name == "postgresql":
        conn.execute(
            text(
                f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {NEW_INDEX} "
                f"ON {TABLE_NAME} (type, booking_id, {CANDIDATE_COLUMN})"
            )
        )
    else:
        conn.execute(
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {NEW_INDEX} "
                f"ON {TABLE_NAME} (type, booking_id, {CANDIDATE_COLUMN})"
            )
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    dialect_name = _dialect_name(conn)

    if dialect_name == "postgresql":
        conn.execute(text(f"DROP INDEX CONCURRENTLY IF EXISTS {NEW_INDEX}"))
    else:
        conn.execute(text(f"DROP INDEX IF EXISTS {NEW_INDEX}"))

    if dialect_name != "sqlite":
        conn.execute(
            text(
                f"ALTER TABLE {TABLE_NAME} ADD CONSTRAINT {OLD_CONSTRAINT} "
                "UNIQUE (type, booking_id)"
            )
        )
    else:
        conn.execute(
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {OLD_CONSTRAINT} "
                f"ON {TABLE_NAME} (type, booking_id)"
            )
        )

    conn.execute(text(f"ALTER TABLE {TABLE_NAME} DROP COLUMN IF EXISTS {CANDIDATE_COLUMN}"))
