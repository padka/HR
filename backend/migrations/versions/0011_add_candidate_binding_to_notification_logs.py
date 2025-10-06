from typing import Tuple

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection


revision = "0011_add_candidate_binding_to_notification_logs"
down_revision = "0010_add_notification_logs"
branch_labels = None
depends_on = None


TABLE_NAME = "notification_logs"
CANDIDATE_COLUMN = "candidate_tg_id"
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


def upgrade(conn: Connection) -> None:
    op, context, standalone_conn = _get_operations(conn)

    try:
        dialect_name = getattr(standalone_conn, "dialect", None)
        dialect_name = dialect_name.name if dialect_name is not None else ""

        with context.begin_transaction():
            op.add_column(
                TABLE_NAME,
                sa.Column(CANDIDATE_COLUMN, sa.BigInteger(), nullable=True),
            )

            if dialect_name == "sqlite":
                op.execute(sa.text(f"DROP INDEX IF EXISTS {OLD_CONSTRAINT}"))
                op.execute(
                    sa.text(
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
                op.execute(
                    sa.text(
                        """
                        CREATE UNIQUE INDEX {name}
                            ON {table} (type, booking_id, {column})
                        """.format(
                            name=NEW_INDEX,
                            table=TABLE_NAME,
                            column=CANDIDATE_COLUMN,
                        )
                    )
                )
            else:
                op.drop_constraint(OLD_CONSTRAINT, TABLE_NAME, type_="unique")
                op.execute(
                    sa.text(
                        """
                        UPDATE {table} nl
                           SET {column} = s.candidate_tg_id
                          FROM slots s
                         WHERE nl.booking_id = s.id
                           AND nl.{column} IS NULL
                           AND s.candidate_tg_id IS NOT NULL
                        """.format(table=TABLE_NAME, column=CANDIDATE_COLUMN)
                    )
                )

                with context.autocommit_block():
                    op.create_index(
                        NEW_INDEX,
                        TABLE_NAME,
                        ["type", "booking_id", CANDIDATE_COLUMN],
                        unique=True,
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
                op.execute(sa.text(f"DROP INDEX IF EXISTS {NEW_INDEX}"))
                op.execute(
                    sa.text(
                        """
                        CREATE UNIQUE INDEX {name}
                            ON {table} (type, booking_id)
                        """.format(name=OLD_CONSTRAINT, table=TABLE_NAME)
                    )
                )
            else:
                with context.autocommit_block():
                    op.drop_index(
                        NEW_INDEX,
                        table_name=TABLE_NAME,
                        postgresql_concurrently=True,
                    )

            if dialect_name != "sqlite":
                op.create_unique_constraint(
                    OLD_CONSTRAINT,
                    TABLE_NAME,
                    ["type", "booking_id"],
                )
            op.drop_column(TABLE_NAME, CANDIDATE_COLUMN)
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()
