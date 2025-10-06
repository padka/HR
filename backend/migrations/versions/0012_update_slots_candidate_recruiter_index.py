from typing import Tuple

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection


revision = "0012_update_slots_candidate_recruiter_index"
down_revision = "0011_add_candidate_binding_to_notification_logs"
branch_labels = None
depends_on = None


TABLE_NAME = "slots"
INDEX_NAME = "uq_slots_candidate_recruiter_active"


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
        dialect_name = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect_name.name if dialect_name is not None else ""

        with context.begin_transaction():
            if dialect_name == "sqlite":
                op.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))
                op.execute(
                    sa.text(
                        """
                        CREATE UNIQUE INDEX {name}
                            ON {table} (candidate_tg_id, recruiter_id)
                         WHERE lower(status) IN ('pending','booked','confirmed_by_candidate')
                        """.format(name=INDEX_NAME, table=TABLE_NAME)
                    )
                )
            else:
                with context.autocommit_block():
                    op.drop_index(
                        INDEX_NAME,
                        table_name=TABLE_NAME,
                        postgresql_concurrently=True,
                    )
                where_clause = sa.text(
                    "lower(status) IN ('pending','booked','confirmed_by_candidate')"
                )
                with context.autocommit_block():
                    op.create_index(
                        INDEX_NAME,
                        TABLE_NAME,
                        ["candidate_tg_id", "recruiter_id"],
                        unique=True,
                        postgresql_where=where_clause,
                        postgresql_concurrently=True,
                    )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    op, context, standalone_conn = _get_operations(conn)

    try:
        dialect_name = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect_name.name if dialect_name is not None else ""

        with context.begin_transaction():
            if dialect_name == "sqlite":
                op.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))
                op.execute(
                    sa.text(
                        """
                        CREATE UNIQUE INDEX {name}
                            ON {table} (candidate_tg_id, recruiter_id)
                         WHERE lower(status) IN ('pending','booked')
                        """.format(name=INDEX_NAME, table=TABLE_NAME)
                    )
                )
            else:
                with context.autocommit_block():
                    op.drop_index(
                        INDEX_NAME,
                        table_name=TABLE_NAME,
                        postgresql_concurrently=True,
                    )
                where_clause = sa.text("lower(status) IN ('pending','booked')")
                with context.autocommit_block():
                    op.create_index(
                        INDEX_NAME,
                        TABLE_NAME,
                        ["candidate_tg_id", "recruiter_id"],
                        unique=True,
                        postgresql_where=where_clause,
                        postgresql_concurrently=True,
                    )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()
