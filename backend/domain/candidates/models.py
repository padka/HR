from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, TYPE_CHECKING
import uuid

import backend.domain.models  # register shared tables (recruiters, cities, slots) for FK resolution
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    BigInteger,
    Float,
    String,
    Text,
    UniqueConstraint,
    Enum as SQLEnum,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.domain.base import Base

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    pass
from backend.domain.candidates.status import CandidateStatus


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, index=True, nullable=True
    )
    username: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, index=True, nullable=True
    )
    telegram_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    telegram_linked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="flow"
    )
    conversation_mode_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fio: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    responsible_recruiter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("recruiters.id", ondelete="SET NULL"), nullable=True
    )
    desired_position: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    resume_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    test1_report_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    test2_report_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    candidate_status: Mapped[Optional[CandidateStatus]] = mapped_column(
        SQLEnum(CandidateStatus, name="candidate_status_enum", create_constraint=True, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        index=True,
    )
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    workflow_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rejection_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    manual_slot_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_slot_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_slot_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manual_slot_timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    manual_slot_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_slot_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    intro_decline_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="bot")

    test_results: Mapped[List["TestResult"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    test2_invites: Mapped[List["Test2Invite"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    interview_note: Mapped[Optional["InterviewNote"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    chat_messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<User {self.id} cid={self.candidate_id} tg={self.telegram_id} status={self.candidate_status}>"


class TestResult(Base):
    __tablename__ = "test_results"
    __test__ = False  # pytest should not treat SQLAlchemy model as a test case

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    raw_score: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    rating: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="bot")
    total_time: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="test_results")
    answers: Mapped[List["QuestionAnswer"]] = relationship(
        back_populates="test_result", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<TestResult {self.id} user={self.user_id} score={self.final_score}>"


class QuestionAnswer(Base):
    __tablename__ = "question_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_result_id: Mapped[int] = mapped_column(
        ForeignKey("test_results.id", ondelete="CASCADE"), nullable=False
    )
    question_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    time_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    overtime: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    test_result: Mapped["TestResult"] = relationship(back_populates="answers")

    __table_args__ = (
        UniqueConstraint("test_result_id", "question_index", name="uq_test_result_question"),
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<QuestionAnswer result={self.test_result_id} index={self.question_index}>"


class Test2InviteStatus(str, Enum):
    CREATED = "created"
    OPENED = "opened"
    COMPLETED = "completed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Test2Invite(Base):
    __tablename__ = "test2_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=Test2InviteStatus.CREATED.value)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_admin: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    user: Mapped["User"] = relationship(back_populates="test2_invites")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<Test2Invite {self.id} candidate={self.candidate_id} status={self.status}>"


class AutoMessage(Base):
    __tablename__ = "auto_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    send_time: Mapped[str] = mapped_column(String(64), nullable=False)
    target_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<AutoMessage {self.id} active={self.is_active}>"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<Notification {self.id} type={self.notification_type}>"


class InterviewNote(Base):
    __tablename__ = "interview_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    interviewer_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="interview_note")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<InterviewNote user_id={self.user_id}>"


class ChatMessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ChatMessageStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    RECEIVED = "received"


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_candidate_created_at", "candidate_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default=ChatMessageDirection.OUTBOUND.value)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="telegram")
    telegram_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ChatMessageStatus.QUEUED.value)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author_label: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    client_request_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="chat_messages")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<ChatMessage {self.id} user={self.candidate_id} dir={self.direction} status={self.status}>"


class CandidateInviteToken(Base):
    __tablename__ = "candidate_invite_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("users.candidate_id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by_telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<CandidateInviteToken {self.id} candidate={self.candidate_id} used={bool(self.used_at)}>"
