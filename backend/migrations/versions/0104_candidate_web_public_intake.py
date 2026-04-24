"""Add public browser candidate campaign intake tables.

This migration is additive-only:
- it creates campaign metadata for global candidate links;
- it creates public intake state with hashed poll/provider/handoff tokens;
- it does not enable runtime public intake or modify existing invite/session flows.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import index_exists, table_exists

revision = "0104_candidate_web_public_intake"
down_revision = "0103_persistent_application_idempotency_keys"
branch_labels = None
depends_on = None


def _build_campaigns_table(metadata: sa.MetaData) -> sa.Table:
    sa.Table("cities", metadata, sa.Column("id", sa.Integer()), extend_existing=True)
    sa.Table("recruiters", metadata, sa.Column("id", sa.Integer()), extend_existing=True)

    return sa.Table(
        "candidate_web_campaigns",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("cities.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "default_recruiter_id",
            sa.Integer(),
            sa.ForeignKey("recruiters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_label", sa.String(length=120), nullable=True),
        sa.Column("utm_defaults_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("allowed_providers_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("slug", name="uq_candidate_web_campaigns_slug"),
        sa.Index("ix_candidate_web_campaigns_status", "status"),
        sa.Index("ix_candidate_web_campaigns_city", "city_id"),
        sa.Index("ix_candidate_web_campaigns_recruiter", "default_recruiter_id"),
    )


def _build_intakes_table(metadata: sa.MetaData) -> sa.Table:
    if "candidate_web_campaigns" not in metadata.tables:
        sa.Table(
            "candidate_web_campaigns",
            metadata,
            sa.Column("id", sa.Integer(), primary_key=True),
            extend_existing=True,
        )
    sa.Table("users", metadata, sa.Column("id", sa.Integer()), extend_existing=True)
    sa.Table(
        "candidate_access_sessions",
        metadata,
        sa.Column("id", sa.BigInteger()),
        extend_existing=True,
    )

    return sa.Table(
        "candidate_web_public_intakes",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("candidate_web_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("poll_token_hash", sa.String(length=128), nullable=False),
        sa.Column("provider_token_hash", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "access_session_id",
            sa.BigInteger(),
            sa.ForeignKey("candidate_access_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("handoff_code_hash", sa.String(length=128), nullable=True),
        sa.Column("utm_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("provider_user_id", sa.String(length=128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.UniqueConstraint("poll_token_hash", name="uq_candidate_web_public_intakes_poll"),
        sa.UniqueConstraint("provider_token_hash", name="uq_candidate_web_public_intakes_provider_token"),
        sa.UniqueConstraint("handoff_code_hash", name="uq_candidate_web_public_intakes_handoff"),
        sa.Index("ix_candidate_web_public_intakes_campaign_id", "campaign_id"),
        sa.Index("ix_candidate_web_public_intakes_campaign_status", "campaign_id", "status"),
        sa.Index("ix_candidate_web_public_intakes_provider_status", "provider", "status"),
        sa.Index("ix_candidate_web_public_intakes_candidate", "candidate_id"),
        sa.Index("ix_candidate_web_public_intakes_expires", "expires_at"),
    )


def upgrade(conn: Connection) -> None:
    metadata = sa.MetaData()
    campaigns = _build_campaigns_table(metadata)
    intakes = _build_intakes_table(metadata)

    for table in (campaigns, intakes):
        if not table_exists(conn, table.name):
            table.create(bind=conn)
        for index in table.indexes:
            if index.name and not index_exists(conn, table.name, index.name):
                index.create(bind=conn)


def downgrade(conn: Connection) -> None:
    """Additive-only policy: no destructive downgrade."""
    _ = conn
