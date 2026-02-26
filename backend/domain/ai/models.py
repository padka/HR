from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.domain.base import Base


class AIOutput(Base):
    __tablename__ = "ai_outputs"
    __table_args__ = (
        UniqueConstraint(
            "scope_type",
            "scope_id",
            "kind",
            "input_hash",
            name="uq_ai_outputs_scope_kind_hash",
        ),
        Index("ix_ai_outputs_scope_kind", "scope_type", "scope_id", "kind"),
        Index("ix_ai_outputs_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AIRequestLog(Base):
    __tablename__ = "ai_request_logs"
    __table_args__ = (
        Index("ix_ai_request_logs_principal_day", "principal_type", "principal_id", "created_at"),
        Index("ix_ai_request_logs_scope", "scope_type", "scope_id", "kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    principal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openai")
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class KnowledgeBaseDocument(Base):
    __tablename__ = "knowledge_base_documents"
    __table_args__ = (
        Index("ix_kb_documents_active_updated", "is_active", "updated_at"),
        Index("ix_kb_documents_category", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_type: Mapped[str] = mapped_column(String(16), nullable=False, default="admin")
    created_by_id: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["KnowledgeBaseChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class KnowledgeBaseChunk(Base):
    __tablename__ = "knowledge_base_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_kb_chunk_doc_index"),
        Index("ix_kb_chunks_document", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_base_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped["KnowledgeBaseDocument"] = relationship(back_populates="chunks")


class AIAgentThread(Base):
    __tablename__ = "ai_agent_threads"
    __table_args__ = (
        UniqueConstraint("principal_type", "principal_id", name="uq_ai_agent_threads_principal"),
        Index("ix_ai_agent_threads_principal", "principal_type", "principal_id"),
        Index("ix_ai_agent_threads_updated", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    principal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Copilot")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["AIAgentMessage"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )


class AIAgentMessage(Base):
    __tablename__ = "ai_agent_messages"
    __table_args__ = (
        Index("ix_ai_agent_messages_thread_time", "thread_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("ai_agent_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")  # user|assistant
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    thread: Mapped["AIAgentThread"] = relationship(back_populates="messages")


class CandidateHHResume(Base):
    __tablename__ = "candidate_hh_resumes"
    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_candidate_hh_resumes_candidate"),
        Index("ix_candidate_hh_resumes_candidate", "candidate_id"),
        Index("ix_candidate_hh_resumes_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="raw_text")
    resume_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_quality_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AIInterviewScriptFeedback(Base):
    __tablename__ = "ai_interview_script_feedback"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ai_interview_script_feedback_idempotency"),
        Index("ix_ai_interview_script_feedback_candidate", "candidate_id", "created_at"),
        Index("ix_ai_interview_script_feedback_outcome", "outcome"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False, default="recruiter")
    principal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    helped: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quick_reasons_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    outcome_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    input_redacted_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_original_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_final_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    labels_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
