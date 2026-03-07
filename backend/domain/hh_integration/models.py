"""ORM models for direct HH integration."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.domain.base import Base
from backend.domain.hh_integration.contracts import (
    HHConnectionStatus,
    HHIdentitySyncStatus,
    HHSyncDirection,
    HHSyncJobStatus,
    HHWebhookDeliveryStatus,
)
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class HHConnection(Base):
    __tablename__ = "hh_connections"
    __table_args__ = (
        UniqueConstraint("principal_type", "principal_id", name="uq_hh_connections_principal"),
        UniqueConstraint("webhook_url_key", name="uq_hh_connections_webhook_key"),
        Index("ix_hh_connections_status", "status"),
        Index("ix_hh_connections_employer", "employer_id", "manager_account_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    principal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    employer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    employer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manager_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=HHConnectionStatus.ACTIVE)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    webhook_url_key: Mapped[str] = mapped_column(String(128), nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    webhook_deliveries = relationship("HHWebhookDelivery", back_populates="connection", cascade="all, delete-orphan")
    sync_jobs = relationship("HHSyncJob", back_populates="connection", cascade="all, delete-orphan")


class CandidateExternalIdentity(Base):
    __tablename__ = "candidate_external_identities"
    __table_args__ = (
        UniqueConstraint("candidate_id", "source", name="uq_candidate_external_identity_candidate"),
        UniqueConstraint("source", "external_negotiation_id", name="uq_candidate_external_identity_negotiation"),
        Index("ix_candidate_external_identity_resume", "source", "external_resume_id"),
        Index("ix_candidate_external_identity_vacancy", "source", "external_vacancy_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="hh")
    external_resume_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_negotiation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_vacancy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_employer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_manager_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_resume_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(24), nullable=False, default=HHIdentitySyncStatus.LINKED)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_hh_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    candidate = relationship("User")


class ExternalVacancyBinding(Base):
    __tablename__ = "external_vacancy_bindings"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "source", name="uq_external_vacancy_binding_vacancy"),
        UniqueConstraint("source", "external_vacancy_id", name="uq_external_vacancy_binding_external"),
        Index("ix_external_vacancy_binding_employer", "external_employer_id", "external_manager_account_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("hh_connections.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="hh")
    external_vacancy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_employer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_manager_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_hh_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    vacancy = relationship("Vacancy")
    connection = relationship("HHConnection")


class HHNegotiation(Base):
    __tablename__ = "hh_negotiations"
    __table_args__ = (
        UniqueConstraint("external_negotiation_id", name="uq_hh_negotiations_external"),
        Index("ix_hh_negotiations_resume_vacancy", "external_resume_id", "external_vacancy_id"),
        Index("ix_hh_negotiations_state", "employer_state", "collection_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("hh_connections.id", ondelete="SET NULL"), nullable=True)
    candidate_identity_id: Mapped[int | None] = mapped_column(ForeignKey("candidate_external_identities.id", ondelete="SET NULL"), nullable=True)
    external_negotiation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_resume_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_vacancy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_employer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_manager_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    collection_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    employer_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    applicant_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actions_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payload_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_hh_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    connection = relationship("HHConnection")
    candidate_identity = relationship("CandidateExternalIdentity")


class HHResumeSnapshot(Base):
    __tablename__ = "hh_resume_snapshots"
    __table_args__ = (
        UniqueConstraint("external_resume_id", name="uq_hh_resume_snapshots_external"),
        Index("ix_hh_resume_snapshots_candidate", "candidate_id", "fetched_at"),
        Index("ix_hh_resume_snapshots_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    external_resume_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    candidate = relationship("User")


class HHSyncJob(Base):
    __tablename__ = "hh_sync_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_hh_sync_jobs_idempotency"),
        Index("ix_hh_sync_jobs_status", "status", "next_retry_at"),
        Index("ix_hh_sync_jobs_entity", "entity_type", "entity_external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("hh_connections.id", ondelete="SET NULL"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(48), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default=HHSyncDirection.INBOUND)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=HHSyncJobStatus.PENDING)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    connection = relationship("HHConnection", back_populates="sync_jobs")


class HHWebhookDelivery(Base):
    __tablename__ = "hh_webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("connection_id", "delivery_id", name="uq_hh_webhook_deliveries_connection_delivery"),
        Index("ix_hh_webhook_deliveries_action", "action_type", "received_at"),
        Index("ix_hh_webhook_deliveries_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("hh_connections.id", ondelete="CASCADE"), nullable=False)
    delivery_id: Mapped[str] = mapped_column(String(128), nullable=False)
    subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    headers_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=HHWebhookDeliveryStatus.RECEIVED)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    connection = relationship("HHConnection", back_populates="webhook_deliveries")
