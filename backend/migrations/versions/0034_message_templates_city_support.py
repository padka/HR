from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection

revision = "0034_message_templates_city_support"
down_revision = "0033_add_intro_decline_reason"
branch_labels = None
depends_on = None

TABLE_OLD = "message_templates"
TABLE_NEW = "message_templates_v2"
TABLE_HISTORY = "message_template_history"


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

    try:
        with context.begin_transaction():
            op.create_table(
                TABLE_NEW,
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("key", sa.String(length=100), nullable=False),
                sa.Column("locale", sa.String(length=16), nullable=False, server_default="ru"),
                sa.Column("channel", sa.String(length=32), nullable=False, server_default="tg"),
                sa.Column("city_id", sa.Integer(), nullable=True),
                sa.Column("body_md", sa.Text(), nullable=False),
                sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
                sa.Column("updated_by", sa.String(length=100), nullable=True),
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
                sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="SET NULL"),
                sa.UniqueConstraint(
                    "key",
                    "locale",
                    "channel",
                    "city_id",
                    "version",
                    name="uq_template_key_locale_channel_version",
                ),
            )

        # Copy existing data into the new table (default city_id=NULL)
        standalone_conn.execute(
            text(
                f"""
                INSERT INTO {TABLE_NEW} (id, key, locale, channel, city_id, body_md, version, is_active, updated_by, created_at, updated_at)
                SELECT id, key, locale, channel, NULL, body_md, version, is_active, NULL,
                       COALESCE(updated_at, CURRENT_TIMESTAMP),
                       COALESCE(updated_at, CURRENT_TIMESTAMP)
                FROM {TABLE_OLD}
                """
            )
        )

        with context.begin_transaction():
            op.drop_table(TABLE_OLD)
            op.rename_table(TABLE_NEW, TABLE_OLD)

        # Indexes for fast lookups
        if dialect_name == "postgresql":
            with context.autocommit_block():
                op.create_index(
                    "ix_template_active_lookup",
                    TABLE_OLD,
                    ["key", "locale", "channel", "city_id", "is_active"],
                    postgresql_concurrently=True,
                )
            with context.autocommit_block():
                op.create_index(
                    "ix_template_city_lookup",
                    TABLE_OLD,
                    ["city_id", "key", "is_active"],
                    postgresql_concurrently=True,
                )
        else:
            with context.begin_transaction():
                op.create_index(
                    "ix_template_active_lookup",
                    TABLE_OLD,
                    ["key", "locale", "channel", "city_id", "is_active"],
                )
                op.create_index(
                    "ix_template_city_lookup",
                    TABLE_OLD,
                    ["city_id", "key", "is_active"],
                )

        # History table
        with context.begin_transaction():
            op.create_table(
                TABLE_HISTORY,
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("template_id", sa.Integer(), nullable=False),
                sa.Column("key", sa.String(length=100), nullable=False),
                sa.Column("locale", sa.String(length=16), nullable=False),
                sa.Column("channel", sa.String(length=32), nullable=False),
                sa.Column("city_id", sa.Integer(), nullable=True),
                sa.Column("body_md", sa.Text(), nullable=False),
                sa.Column("version", sa.Integer(), nullable=False),
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
                sa.Column("updated_by", sa.String(length=100), nullable=True),
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
                sa.ForeignKeyConstraint(["template_id"], [f"{TABLE_OLD}.id"], ondelete="CASCADE"),
                sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="SET NULL"),
            )

        # Seed initial history records
        now = datetime.now(timezone.utc)
        standalone_conn.execute(
            text(
                f"""
                INSERT INTO {TABLE_HISTORY} (
                    template_id, key, locale, channel, city_id, body_md, version, is_active, updated_by, created_at, updated_at
                )
                SELECT id, key, locale, channel, city_id, body_md, version, is_active, updated_by,
                       COALESCE(created_at, :now), COALESCE(updated_at, :now)
                FROM {TABLE_OLD}
                """
            ),
            {"now": now},
        )
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()


def downgrade(conn: Connection) -> None:  # pragma: no cover - rollback helper
    op, context, standalone_conn = _get_operations(conn)
    try:
        with context.begin_transaction():
            op.drop_table(TABLE_HISTORY)
    finally:
        if standalone_conn is not conn:
            standalone_conn.close()
