from typing import Tuple

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection


revision = "0015_add_candidate_test_outcomes"
down_revision = "0014_notification_outbox_and_templates"
branch_labels = None
depends_on = None


TABLE_OUTCOMES = "candidate_test_outcomes"
TABLE_DELIVERIES = "candidate_test_outcome_deliveries"


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
    dialect = getattr(standalone_conn, "dialect", None)
    dialect_name = dialect.name if dialect is not None else ""

    with context.begin_transaction():
        op.create_table(
            TABLE_OUTCOMES,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("test_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("rating", sa.String(length=50), nullable=True),
            sa.Column("score", sa.Float(), nullable=False, server_default=sa.text("0")),
            sa.Column("correct_answers", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("total_questions", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("attempt_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("artifact_path", sa.String(length=255), nullable=False),
            sa.Column("artifact_name", sa.String(length=255), nullable=False),
            sa.Column("artifact_mime", sa.String(length=100), nullable=False),
            sa.Column("artifact_size", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "user_id",
                "test_id",
                "attempt_at",
                name="uq_candidate_test_outcome_attempt",
            ),
        )

        op.create_table(
            TABLE_DELIVERIES,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("outcome_id", sa.Integer(), nullable=False),
            sa.Column("chat_id", sa.BigInteger(), nullable=False),
            sa.Column(
                "delivered_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("message_id", sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(
                ["outcome_id"], [f"{TABLE_OUTCOMES}.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint(
                "outcome_id",
                "chat_id",
                name="uq_candidate_test_outcome_delivery",
            ),
        )

    if dialect_name == "postgresql":
        with context.autocommit_block():
            op.create_index(
                "ix_candidate_test_outcomes_user",
                TABLE_OUTCOMES,
                ["user_id", "attempt_at"],
                postgresql_concurrently=True,
            )
        with context.autocommit_block():
            op.create_index(
                "ix_candidate_test_outcome_deliveries_chat",
                TABLE_DELIVERIES,
                ["chat_id"],
                postgresql_concurrently=True,
            )
    else:
        with context.begin_transaction():
            op.create_index(
                "ix_candidate_test_outcomes_user",
                TABLE_OUTCOMES,
                ["user_id", "attempt_at"],
            )
            op.create_index(
                "ix_candidate_test_outcome_deliveries_chat",
                TABLE_DELIVERIES,
                ["chat_id"],
            )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    op, context, _ = _get_operations(conn)
    with context.begin_transaction():
        op.drop_index("ix_candidate_test_outcome_deliveries_chat", table_name=TABLE_DELIVERIES)
        op.drop_index("ix_candidate_test_outcomes_user", table_name=TABLE_OUTCOMES)
        op.drop_table(TABLE_DELIVERIES)
        op.drop_table(TABLE_OUTCOMES)
