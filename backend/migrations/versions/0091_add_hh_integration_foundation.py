"""Add foundation tables for direct HeadHunter integration."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

revision = "0091_add_hh_integration_foundation"
down_revision = "0090_add_messenger_fields"
branch_labels = None
depends_on = None


def _tables(metadata: sa.MetaData) -> list[sa.Table]:
    # Register referenced parent tables in this metadata so FK resolution works
    # when the migration creates only the HH integration tables.
    sa.Table("users", metadata, sa.Column("id", sa.Integer()), extend_existing=True)
    sa.Table("vacancies", metadata, sa.Column("id", sa.Integer()), extend_existing=True)

    hh_connections = sa.Table(
        "hh_connections",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("principal_id", sa.Integer(), nullable=False),
        sa.Column("employer_id", sa.String(length=64), nullable=True),
        sa.Column("employer_name", sa.String(length=255), nullable=True),
        sa.Column("manager_id", sa.String(length=64), nullable=True),
        sa.Column("manager_account_id", sa.String(length=64), nullable=True),
        sa.Column("manager_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("webhook_url_key", sa.String(length=128), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("profile_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.UniqueConstraint("principal_type", "principal_id", name="uq_hh_connections_principal"),
        sa.UniqueConstraint("webhook_url_key", name="uq_hh_connections_webhook_key"),
        sa.Index("ix_hh_connections_status", "status"),
        sa.Index("ix_hh_connections_employer", "employer_id", "manager_account_id"),
    )

    candidate_external_identities = sa.Table(
        "candidate_external_identities",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="hh"),
        sa.Column("external_resume_id", sa.String(length=64), nullable=True),
        sa.Column("external_negotiation_id", sa.String(length=64), nullable=True),
        sa.Column("external_vacancy_id", sa.String(length=64), nullable=True),
        sa.Column("external_employer_id", sa.String(length=64), nullable=True),
        sa.Column("external_manager_id", sa.String(length=64), nullable=True),
        sa.Column("external_resume_url", sa.String(length=255), nullable=True),
        sa.Column("sync_status", sa.String(length=24), nullable=False, server_default="linked"),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("last_hh_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.UniqueConstraint("candidate_id", "source", name="uq_candidate_external_identity_candidate"),
        sa.UniqueConstraint("source", "external_negotiation_id", name="uq_candidate_external_identity_negotiation"),
        sa.Index("ix_candidate_external_identity_resume", "source", "external_resume_id"),
        sa.Index("ix_candidate_external_identity_vacancy", "source", "external_vacancy_id"),
    )

    external_vacancy_bindings = sa.Table(
        "external_vacancy_bindings",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("hh_connections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="hh"),
        sa.Column("external_vacancy_id", sa.String(length=64), nullable=False),
        sa.Column("external_employer_id", sa.String(length=64), nullable=True),
        sa.Column("external_manager_account_id", sa.String(length=64), nullable=True),
        sa.Column("external_url", sa.String(length=255), nullable=True),
        sa.Column("title_snapshot", sa.String(length=255), nullable=True),
        sa.Column("payload_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_hh_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.UniqueConstraint("vacancy_id", "source", name="uq_external_vacancy_binding_vacancy"),
        sa.UniqueConstraint("source", "external_vacancy_id", name="uq_external_vacancy_binding_external"),
        sa.Index("ix_external_vacancy_binding_employer", "external_employer_id", "external_manager_account_id"),
    )

    hh_negotiations = sa.Table(
        "hh_negotiations",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("hh_connections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("candidate_identity_id", sa.Integer(), sa.ForeignKey("candidate_external_identities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_negotiation_id", sa.String(length=64), nullable=False),
        sa.Column("external_resume_id", sa.String(length=64), nullable=True),
        sa.Column("external_vacancy_id", sa.String(length=64), nullable=True),
        sa.Column("external_employer_id", sa.String(length=64), nullable=True),
        sa.Column("external_manager_id", sa.String(length=64), nullable=True),
        sa.Column("collection_name", sa.String(length=64), nullable=True),
        sa.Column("employer_state", sa.String(length=64), nullable=True),
        sa.Column("applicant_state", sa.String(length=64), nullable=True),
        sa.Column("actions_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("payload_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_hh_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.UniqueConstraint("external_negotiation_id", name="uq_hh_negotiations_external"),
        sa.Index("ix_hh_negotiations_resume_vacancy", "external_resume_id", "external_vacancy_id"),
        sa.Index("ix_hh_negotiations_state", "employer_state", "collection_name"),
    )

    hh_resume_snapshots = sa.Table(
        "hh_resume_snapshots",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_resume_id", sa.String(length=64), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.UniqueConstraint("external_resume_id", name="uq_hh_resume_snapshots_external"),
        sa.Index("ix_hh_resume_snapshots_candidate", "candidate_id", "fetched_at"),
        sa.Index("ix_hh_resume_snapshots_content_hash", "content_hash"),
    )

    hh_sync_jobs = sa.Table(
        "hh_sync_jobs",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("hh_connections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_type", sa.String(length=48), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default="inbound"),
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("entity_external_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.UniqueConstraint("idempotency_key", name="uq_hh_sync_jobs_idempotency"),
        sa.Index("ix_hh_sync_jobs_status", "status", "next_retry_at"),
        sa.Index("ix_hh_sync_jobs_entity", "entity_type", "entity_external_id"),
    )

    hh_webhook_deliveries = sa.Table(
        "hh_webhook_deliveries",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("hh_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delivery_id", sa.String(length=128), nullable=False),
        sa.Column("subscription_id", sa.String(length=64), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("headers_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="received"),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP" if metadata.bind and metadata.bind.dialect.name == "sqlite" else "NOW()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("connection_id", "delivery_id", name="uq_hh_webhook_deliveries_connection_delivery"),
        sa.Index("ix_hh_webhook_deliveries_action", "action_type", "received_at"),
        sa.Index("ix_hh_webhook_deliveries_status", "status"),
    )

    return [
        hh_connections,
        candidate_external_identities,
        external_vacancy_bindings,
        hh_negotiations,
        hh_resume_snapshots,
        hh_sync_jobs,
        hh_webhook_deliveries,
    ]


def upgrade(conn: Connection) -> None:
    metadata = sa.MetaData()
    metadata.bind = conn
    tables = _tables(metadata)
    metadata.create_all(conn, tables=tables, checkfirst=True)


def downgrade(conn: Connection) -> None:  # pragma: no cover
    metadata = sa.MetaData()
    metadata.bind = conn
    tables = _tables(metadata)
    metadata.drop_all(conn, tables=list(reversed(tables)), checkfirst=True)
