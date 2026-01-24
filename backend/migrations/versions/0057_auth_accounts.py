"""Add auth_accounts table for web principals"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    text,
)

revision = "0057_auth_accounts"
down_revision = "0056_sync_workflow_status_from_legacy"

metadata = MetaData()


auth_accounts = Table(
    "auth_accounts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(120), nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("principal_type", String(16), nullable=False),
    Column("principal_id", Integer, nullable=False),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ),
    UniqueConstraint("username", name="uq_auth_accounts_username"),
)


def upgrade(conn):
    auth_accounts.create(conn, checkfirst=True)


def downgrade(conn):
    auth_accounts.drop(conn, checkfirst=True)
