from typing import Tuple

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection


revision = "0019_fix_notification_log_unique_index"
down_revision = "0018_candidate_report_urls"
branch_labels = None
depends_on = None


TABLE_NAME = "notification_logs"
OLD_CONSTRAINT = "uq_notification_logs_type_booking"
NEW_INDEX = "uq_notif_type_booking_candidate"


def _get_operations(conn: Connection) -> Tuple[Operations, MigrationContext, Connection]:
    engine = getattr(conn, "engine", None)
    standalone_conn = engine.connect() if engine is not None else conn
    if engine is not None and engine.dialect.name == "sqlite" and standalone_conn is not conn:
        standalone_conn.close()
        standalone_conn = conn
    context = MigrationContext.configure(connection=standalone_conn)
    return Operations(context), context, standalone_conn


def _populate_missing_candidate_ids(op: Operations) -> None:
    op.execute(
        sa.text(
            f"""
            UPDATE {TABLE_NAME} AS nl
               SET candidate_tg_id = (
                   SELECT s.candidate_tg_id
                     FROM slots AS s
                    WHERE s.id = nl.booking_id
               )
             WHERE nl.candidate_tg_id IS NULL
               AND EXISTS (
                   SELECT 1
                     FROM slots AS s
                    WHERE s.id = nl.booking_id
                      AND s.candidate_tg_id IS NOT NULL
               )
            """
        )
    )


def upgrade(conn: Connection) -> None:
    op, context, standalone_conn = _get_operations(conn)
    try:
        dialect = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect.name if dialect is not None else ""

        with context.begin_transaction():
            _populate_missing_candidate_ids(op)
            if dialect_name == "sqlite":
                op.execute(sa.text(f"DROP INDEX IF EXISTS {OLD_CONSTRAINT}"))
                op.execute(
                    sa.text(
                        f"""
                        CREATE UNIQUE INDEX IF NOT EXISTS {NEW_INDEX}
                            ON {TABLE_NAME} (type, booking_id, candidate_tg_id)
                        """
                    )
                )
            else:
                op.execute(
                    sa.text(
                        f"""
                        ALTER TABLE {TABLE_NAME}
                        DROP CONSTRAINT IF EXISTS {OLD_CONSTRAINT}
                        """
                    )
                )
                op.execute(sa.text(f"DROP INDEX IF EXISTS {OLD_CONSTRAINT}"))
                with context.autocommit_block():
                    op.execute(
                        sa.text(
                            f"""
                            CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {NEW_INDEX}
                                ON {TABLE_NAME} (type, booking_id, candidate_tg_id)
                            """
                        )
                    )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    op, context, standalone_conn = _get_operations(conn)
    try:
        dialect = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect.name if dialect is not None else ""

        with context.begin_transaction():
            if dialect_name == "sqlite":
                op.execute(sa.text(f"DROP INDEX IF EXISTS {NEW_INDEX}"))
                op.execute(
                    sa.text(
                        f"""
                        CREATE UNIQUE INDEX IF NOT EXISTS {OLD_CONSTRAINT}
                            ON {TABLE_NAME} (type, booking_id)
                        """
                    )
                )
            else:
                with context.autocommit_block():
                    op.execute(
                        sa.text(
                            f"""
                            DROP INDEX IF EXISTS {NEW_INDEX}
                            """
                        )
                    )
                op.execute(
                    sa.text(
                        f"""
                        ALTER TABLE {TABLE_NAME}
                        ADD CONSTRAINT {OLD_CONSTRAINT}
                        UNIQUE (type, booking_id)
                        """
                    )
                )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()
