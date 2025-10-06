"""Introduce notification and callback logs, extend slot status column."""

from __future__ import annotations

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Connection


revision = "0010_add_notification_logs"
down_revision = "0009_add_missing_indexes"
branch_labels = None
depends_on = None


def _get_operations(conn: Connection) -> tuple[Operations, MigrationContext]:
    context = MigrationContext.configure(connection=conn)
    return Operations(context), context


def upgrade(conn: Connection) -> None:
    op, context = _get_operations(conn)
    dialect_name = conn.dialect.name
    with context.begin_transaction():
        if dialect_name == "sqlite":
            with op.batch_alter_table("slots") as batch_op:
                batch_op.alter_column(
                    "status",
                    existing_type=sa.String(length=20),
                    type_=sa.String(length=32),
                    existing_nullable=False,
                )
        else:
            op.alter_column(
                "slots",
                "status",
                existing_type=sa.String(length=20),
                type_=sa.String(length=32),
                existing_nullable=False,
            )

        op.create_table(
            "notification_logs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("booking_id", sa.Integer, nullable=False),
            sa.Column("type", sa.String(length=50), nullable=False),
            sa.Column("payload", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["booking_id"],
                ["slots.id"],
                name="fk_notification_logs_booking_id",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("type", "booking_id", name="uq_notification_logs_type_booking"),
        )

        op.create_table(
            "telegram_callback_logs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("callback_id", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("callback_id", name="uq_telegram_callback_logs_callback_id"),
        )


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    op, context = _get_operations(conn)
    dialect_name = conn.dialect.name
    with context.begin_transaction():
        op.drop_table("telegram_callback_logs")
        op.drop_table("notification_logs")
        if dialect_name == "sqlite":
            with op.batch_alter_table("slots") as batch_op:
                batch_op.alter_column(
                    "status",
                    existing_type=sa.String(length=32),
                    type_=sa.String(length=20),
                    existing_nullable=False,
                )
        else:
            op.alter_column(
                "slots",
                "status",
                existing_type=sa.String(length=32),
                type_=sa.String(length=20),
                existing_nullable=False,
            )
