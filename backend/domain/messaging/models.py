from __future__ import annotations

import uuid
from datetime import UTC, datetime

import backend.domain.candidates.models  # noqa: F401 - register candidate tables for FK resolution
import backend.domain.models  # noqa: F401 - register shared/core tables for FK resolution
from backend.domain.base import Base
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


def _uuid_str() -> str:
    return str(uuid.uuid4())


class MessageThread(Base):
    __tablename__ = "message_threads"
    __table_args__ = (
        Index("ix_message_threads_candidate_updated", "candidate_id", "updated_at"),
        Index("ix_message_threads_application_updated", "application_id", "updated_at"),
        Index("ix_message_threads_status_updated", "status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    thread_uuid: Mapped[str] = mapped_column(
        String(36), nullable=False, default=_uuid_str, index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requisition_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("requisitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thread_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    purpose_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    source_entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    current_primary_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Deferred FK to avoid the message_threads <-> messages cycle during table creation.
    last_message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "messages.id",
            name="fk_message_threads_last_message_id",
            use_alter=True,
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    thread_context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="thread",
        cascade="all, delete-orphan",
        foreign_keys="Message.thread_id",
    )
    last_message: Mapped[Message | None] = relationship(
        "Message",
        foreign_keys=[last_message_id],
        post_update=True,
        uselist=False,
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_messages_idempotency_key"),
        Index("ix_messages_thread_created", "thread_id", "created_at"),
        Index("ix_messages_candidate_created", "candidate_id", "created_at"),
        Index("ix_messages_application_intent_created", "application_id", "intent_key", "created_at"),
        Index("ix_messages_dedupe_created", "dedupe_scope_key", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_uuid: Mapped[str] = mapped_column(
        String(36), nullable=False, default=_uuid_str, index=True
    )
    thread_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("message_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requisition_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("requisitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    intent_key: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sender_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_family_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    template_context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    canonical_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    render_context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dedupe_scope_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    intent_status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    thread: Mapped[MessageThread] = relationship(
        "MessageThread",
        back_populates="messages",
        foreign_keys=[thread_id],
    )
    replies: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="reply_to_message",
        foreign_keys="Message.reply_to_message_id",
    )
    reply_to_message: Mapped[Message | None] = relationship(
        "Message",
        remote_side=lambda: [Message.id],
        foreign_keys=[reply_to_message_id],
        back_populates="replies",
        uselist=False,
    )
    deliveries: Mapped[list[MessageDelivery]] = relationship(
        "MessageDelivery",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class MessageDelivery(Base):
    __tablename__ = "message_deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_message_deliveries_idempotency_key"),
        Index("ix_message_deliveries_message_attempt", "message_id", "overall_attempt_no"),
        Index("ix_message_deliveries_candidate_channel_created", "candidate_id", "channel", "created_at"),
        Index("ix_message_deliveries_status_retry", "delivery_status", "next_retry_at"),
        Index("ix_message_deliveries_provider_message", "provider", "provider_message_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    delivery_uuid: Mapped[str] = mapped_column(
        String(36), nullable=False, default=_uuid_str, index=True
    )
    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("message_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    identity_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("candidate_channel_identities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    destination_fingerprint: Mapped[str | None] = mapped_column(String(160), nullable=True)
    route_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    channel_attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    overall_attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    delivery_status: Mapped[str] = mapped_column(String(24), nullable=False)
    failure_class: Mapped[str | None] = mapped_column(String(16), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rendered_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    message: Mapped[Message] = relationship("Message", back_populates="deliveries")
    receipts: Mapped[list[ProviderReceipt]] = relationship(
        "ProviderReceipt",
        back_populates="delivery",
        cascade="all, delete-orphan",
    )


class ProviderReceipt(Base):
    __tablename__ = "provider_receipts"
    __table_args__ = (
        Index(
            "uq_provider_receipts_provider_event_present",
            "provider",
            "provider_event_id",
            unique=True,
            sqlite_where=text("provider_event_id IS NOT NULL"),
            postgresql_where=text("provider_event_id IS NOT NULL"),
        ),
        Index("ix_provider_receipts_delivery_time", "delivery_id", "occurred_at"),
        Index("ix_provider_receipts_provider_message", "provider", "provider_message_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    receipt_uuid: Mapped[str] = mapped_column(
        String(36), nullable=False, default=_uuid_str, index=True
    )
    delivery_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("message_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    receipt_type: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_status_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_status_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_failure_class: Mapped[str | None] = mapped_column(String(16), nullable=True)
    normalized_failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    delivery: Mapped[MessageDelivery] = relationship("MessageDelivery", back_populates="receipts")


class CandidateContactPolicy(Base):
    __tablename__ = "candidate_contact_policies"
    __table_args__ = (
        Index(
            "uq_candidate_contact_policies_candidate_purpose",
            "candidate_id",
            "purpose_scope",
            unique=True,
            sqlite_where=text("application_id IS NULL"),
            postgresql_where=text("application_id IS NULL"),
        ),
        Index(
            "uq_candidate_contact_policies_candidate_application_purpose",
            "candidate_id",
            "application_id",
            "purpose_scope",
            unique=True,
            sqlite_where=text("application_id IS NOT NULL"),
            postgresql_where=text("application_id IS NOT NULL"),
        ),
        Index("ix_candidate_contact_policies_preferred_channel", "preferred_channel"),
        Index("ix_candidate_contact_policies_do_not_contact_updated", "do_not_contact", "updated_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    purpose_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    preferred_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fallback_order_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    fallback_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    consent_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    serviceability_status: Mapped[str] = mapped_column(String(24), nullable=False, default="serviceable")
    do_not_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quiet_windows_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    max_messages_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_spacing_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ChannelHealthRegistry(Base):
    __tablename__ = "channel_health_registry"
    __table_args__ = (
        UniqueConstraint(
            "channel",
            "provider",
            "runtime_surface",
            name="uq_channel_health_registry_triplet",
        ),
        Index("ix_channel_health_registry_health_updated", "health_status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    runtime_surface: Mapped[str] = mapped_column(String(32), nullable=False)
    health_status: Mapped[str] = mapped_column(String(24), nullable=False, default="healthy")
    failure_domain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    circuit_state: Mapped[str] = mapped_column(String(24), nullable=False, default="closed")
    last_probe_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    probe_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


__all__ = [
    "MessageThread",
    "Message",
    "MessageDelivery",
    "ProviderReceipt",
    "CandidateContactPolicy",
    "ChannelHealthRegistry",
]
