"""Add analytics_events table and use_jinja flag to message_templates.

Revision ID: 0035_add_analytics_events_and_jinja_flag
Revises: 0034_message_templates_city_support
Create Date: 2025-12-01 15:30:00.000000

"""

from __future__ import annotations

from typing import Tuple

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection

revision = "0035_add_analytics_events_and_jinja_flag"
down_revision = "0034_message_templates_city_support"
branch_labels = None
depends_on = None


def _get_operations(conn: Connection) -> Tuple[Operations, MigrationContext, Connection]:
    """Get Alembic operations object for this connection."""
    engine = getattr(conn, "engine", None)
    standalone_conn = engine.connect() if engine is not None else conn
    if engine is not None and engine.dialect.name == "sqlite" and standalone_conn is not conn:
        standalone_conn.close()
        standalone_conn = conn
    context = MigrationContext.configure(connection=standalone_conn)
    return Operations(context), context, standalone_conn


def upgrade(conn: Connection) -> None:
    """Apply migration: add analytics_events table and use_jinja flag."""
    op, context, standalone_conn = _get_operations(conn)
    dialect = getattr(standalone_conn, "dialect", None)
    dialect_name = dialect.name if dialect is not None else ""

    try:
        # Create analytics_events table
        with context.begin_transaction():
            # Determine timestamp default based on dialect
            timestamp_default = (
                sa.text("CURRENT_TIMESTAMP")
                if dialect_name == "postgresql"
                else sa.text("(datetime('now'))")
            )

            op.create_table(
                "analytics_events",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("event_name", sa.String(length=100), nullable=False),
                sa.Column("user_id", sa.BigInteger(), nullable=True),
                sa.Column("candidate_id", sa.Integer(), nullable=True),
                sa.Column("city_id", sa.Integer(), nullable=True),
                sa.Column("slot_id", sa.Integer(), nullable=True),
                sa.Column("booking_id", sa.Integer(), nullable=True),
                sa.Column(
                    "metadata",
                    sa.Text(),  # Store JSON as text for cross-DB compatibility
                    nullable=True,
                ),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=timestamp_default,
                    nullable=False,
                ),
            )

        # Create indexes for efficient querying
        with context.begin_transaction():
            op.create_index(
                "idx_analytics_events_event_name",
                "analytics_events",
                ["event_name"],
            )
            op.create_index(
                "idx_analytics_events_candidate_id",
                "analytics_events",
                ["candidate_id"],
            )
            op.create_index(
                "idx_analytics_events_created_at",
                "analytics_events",
                ["created_at"],
            )
            op.create_index(
                "idx_analytics_events_user_id",
                "analytics_events",
                ["user_id"],
            )

        # Add use_jinja flag to message_templates
        # This allows gradual migration from .format() to Jinja2
        with context.begin_transaction():
            # Determine boolean default based on dialect
            bool_default = sa.text("false") if dialect_name == "postgresql" else sa.text("0")

            op.add_column(
                "message_templates",
                sa.Column(
                    "use_jinja",
                    sa.Boolean(),
                    nullable=False,
                    server_default=bool_default,
                ),
            )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    """Revert migration: drop analytics_events table and use_jinja flag."""
    op, context, standalone_conn = _get_operations(conn)

    try:
        # Drop indexes first
        with context.begin_transaction():
            op.drop_index("idx_analytics_events_user_id", table_name="analytics_events")
            op.drop_index("idx_analytics_events_created_at", table_name="analytics_events")
            op.drop_index("idx_analytics_events_candidate_id", table_name="analytics_events")
            op.drop_index("idx_analytics_events_event_name", table_name="analytics_events")

        # Drop analytics_events table
        with context.begin_transaction():
            op.drop_table("analytics_events")

        # Remove use_jinja column from message_templates
        with context.begin_transaction():
            op.drop_column("message_templates", "use_jinja")
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()
