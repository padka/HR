"""Add persistent application idempotency ledger table.

This migration is intentionally additive-only:
- it creates the application_idempotency_keys ledger required by RS-IDEMP-019;
- it does not backfill data;
- it does not modify application_events uniqueness;
- it does not wire runtime flows to the new ledger.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from backend.migrations.utils import index_exists, table_exists

revision = "0103_persistent_application_idempotency_keys"
down_revision = "0102_phase_a_schema_foundation"
branch_labels = None
depends_on = None


def _build_table(metadata: sa.MetaData) -> sa.Table:
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer()),
        extend_existing=True,
    )
    sa.Table(
        "applications",
        metadata,
        sa.Column("id", sa.BigInteger()),
        extend_existing=True,
    )
    sa.Table(
        "requisitions",
        metadata,
        sa.Column("id", sa.BigInteger()),
        extend_existing=True,
    )

    return sa.Table(
        "application_idempotency_keys",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("operation_kind", sa.String(length=32), nullable=False),
        sa.Column("producer_family", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("requisition_id", sa.BigInteger(), sa.ForeignKey("requisitions.id"), nullable=True),
        sa.Column("event_id", sa.String(length=36), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("source_system", sa.String(length=32), nullable=True),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
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
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint(
            "operation_kind",
            "producer_family",
            "idempotency_key",
            name="uq_application_idempotency_keys_scope",
        ),
        sa.Index("ix_application_idempotency_keys_candidate_id", "candidate_id"),
        sa.Index("ix_application_idempotency_keys_application_id", "application_id"),
        sa.Index("ix_application_idempotency_keys_requisition_id", "requisition_id"),
        sa.Index("ix_application_idempotency_keys_event_id", "event_id"),
        sa.Index("ix_application_idempotency_keys_correlation_id", "correlation_id"),
        sa.Index(
            "ix_application_idempotency_keys_status_created_at",
            "status",
            "created_at",
        ),
        sa.Index("ix_application_idempotency_keys_expires_at", "expires_at"),
    )


def upgrade(conn: Connection) -> None:
    metadata = sa.MetaData()
    table = _build_table(metadata)

    if not table_exists(conn, table.name):
        table.create(bind=conn)

    expected_indexes = {
        "ix_application_idempotency_keys_candidate_id",
        "ix_application_idempotency_keys_application_id",
        "ix_application_idempotency_keys_requisition_id",
        "ix_application_idempotency_keys_event_id",
        "ix_application_idempotency_keys_correlation_id",
        "ix_application_idempotency_keys_status_created_at",
        "ix_application_idempotency_keys_expires_at",
    }
    for index in table.indexes:
        if index.name in expected_indexes and not index_exists(conn, table.name, index.name):
            index.create(bind=conn)


def downgrade(conn: Connection) -> None:
    """Additive-only policy: no destructive downgrade."""
    _ = conn
