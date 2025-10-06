from typing import Tuple

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection


revision = "0013_enhance_notification_logs"
down_revision = "0012_update_slots_candidate_recruiter_index"
branch_labels = None
depends_on = None


TABLE_NAME = "notification_logs"
STATUS_COLUMN = "status"
ATTEMPTS_COLUMN = "attempts"
LAST_ERROR_COLUMN = "last_error"
NEXT_RETRY_COLUMN = "next_retry_at"


def _get_operations(conn: Connection) -> Tuple[Operations, MigrationContext, Connection]:
    engine = getattr(conn, "engine", None)
    standalone_conn = engine.connect() if engine is not None else conn
    if engine is not None and engine.dialect.name == "sqlite" and standalone_conn is not conn:
        standalone_conn.close()
        standalone_conn = conn
    context = MigrationContext.configure(connection=standalone_conn)
    return Operations(context), context, standalone_conn


def upgrade(conn: Connection) -> None:
    op, context, standalone_conn = _get_operations(conn)
    try:
        dialect = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect.name if dialect is not None else ""

        with context.begin_transaction():
            op.add_column(
                TABLE_NAME,
                sa.Column(STATUS_COLUMN, sa.String(length=20), nullable=False, server_default="sent"),
            )
            op.add_column(
                TABLE_NAME,
                sa.Column(ATTEMPTS_COLUMN, sa.Integer(), nullable=False, server_default="1"),
            )
            op.add_column(
                TABLE_NAME,
                sa.Column(LAST_ERROR_COLUMN, sa.Text(), nullable=True),
            )
            op.add_column(
                TABLE_NAME,
                sa.Column(NEXT_RETRY_COLUMN, sa.DateTime(timezone=True), nullable=True),
            )

        if dialect_name != "sqlite":
            with context.begin_transaction():
                op.alter_column(TABLE_NAME, STATUS_COLUMN, server_default=None)
                op.alter_column(TABLE_NAME, ATTEMPTS_COLUMN, server_default=None)
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    op, context, standalone_conn = _get_operations(conn)
    try:
        with context.begin_transaction():
            op.drop_column(TABLE_NAME, NEXT_RETRY_COLUMN)
            op.drop_column(TABLE_NAME, LAST_ERROR_COLUMN)
            op.drop_column(TABLE_NAME, ATTEMPTS_COLUMN)
            op.drop_column(TABLE_NAME, STATUS_COLUMN)
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()
