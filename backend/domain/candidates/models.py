from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import TYPE_CHECKING, List, Optional

import backend.domain.models  # noqa: F401 - register shared tables (recruiters, cities, slots) for FK resolution
from sqlalchemy import (
    Boolean,
    BigInteger,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.sql import func

from backend.domain.base import Base
from backend.domain.candidates.phones import normalize_candidate_phone
from backend.domain.candidates.status import CandidateStatus

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_workflow_status", "workflow_status"),
        Index("ix_users_responsible_recruiter", "responsible_recruiter_id"),
        Index("ix_users_phone_normalized", "phone_normalized"),
    )

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
    phone_normalized: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
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
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    archive_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    archive_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    final_outcome: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    final_outcome_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    manual_slot_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_slot_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_slot_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manual_slot_timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    manual_slot_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_slot_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    intro_decline_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="bot")

    # hh.ru integration fields
    hh_resume_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hh_negotiation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hh_vacancy_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hh_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hh_sync_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    hh_sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Messenger integration fields
    messenger_platform: Mapped[str] = mapped_column(
        String(20), nullable=False, default="telegram"
    )
    max_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

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
    chat_read_states: Mapped[List["CandidateChatRead"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    chat_workspace: Mapped[Optional["CandidateChatWorkspace"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    journey_events: Mapped[List["CandidateJourneyEvent"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="CandidateJourneyEvent.created_at.desc()",
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<User {self.id} cid={self.candidate_id} tg={self.telegram_id} status={self.candidate_status}>"

    @validates("phone")
    def _sync_phone_normalized(self, _key: str, value: Optional[str]) -> Optional[str]:
        clean_value = str(value or "").strip() or None
        self.phone_normalized = normalize_candidate_phone(clean_value)
        return clean_value


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


class CandidateJourneyEvent(Base):
    __tablename__ = "candidate_journey_events"
    __table_args__ = (
        Index("ix_candidate_journey_events_candidate_created", "candidate_id", "created_at"),
        Index("ix_candidate_journey_events_event_key", "event_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_key: Mapped[str] = mapped_column(String(80), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status_slug: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    candidate: Mapped["User"] = relationship(back_populates="journey_events")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<CandidateJourneyEvent {self.id} candidate={self.candidate_id} key={self.event_key}>"


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


class CandidateChatRead(Base):
    __tablename__ = "candidate_chat_reads"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "principal_type",
            "principal_id",
            name="uq_candidate_chat_reads_principal",
        ),
        Index(
            "ix_candidate_chat_reads_principal",
            "principal_type",
            "principal_id",
            "last_read_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    principal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    last_read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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

    user: Mapped["User"] = relationship(back_populates="chat_read_states")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return (
            f"<CandidateChatRead candidate={self.candidate_id} "
            f"principal={self.principal_type}:{self.principal_id}>"
        )


class CandidateChatWorkspace(Base):
    __tablename__ = "candidate_chat_workspaces"
    __table_args__ = (
        UniqueConstraint("candidate_id", name="uq_candidate_chat_workspaces_candidate"),
        Index("ix_candidate_chat_workspaces_updated", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shared_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agreements_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    follow_up_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
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

    user: Mapped["User"] = relationship(back_populates="chat_workspace")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<CandidateChatWorkspace candidate={self.candidate_id}>"


class CandidateInviteToken(Base):
    __tablename__ = "candidate_invite_tokens"
    __table_args__ = (
        Index(
            "ix_candidate_invite_tokens_candidate_channel_status",
            "candidate_id",
            "channel",
            "status",
        ),
        Index(
            "uq_candidate_invite_tokens_active_max_candidate",
            "candidate_id",
            unique=True,
            sqlite_where=text("status = 'active' AND channel = 'max'"),
            postgresql_where=text("status = 'active' AND channel = 'max'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("users.candidate_id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="generic")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by_telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    used_by_external_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<CandidateInviteToken {self.id} candidate={self.candidate_id} used={bool(self.used_at)}>"


class CandidateJourneySessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    BLOCKED = "blocked"


class CandidateJourneyStepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class CandidateJourneySurface(str, Enum):
    STANDALONE_WEB = "standalone_web"
    TELEGRAM_WEBAPP = "telegram_webapp"
    MAX_MINIAPP = "max_miniapp"
    MAX_CHAT = "max_chat"


class CandidateAccessTokenKind(str, Enum):
    INVITE = "invite"
    LAUNCH = "launch"
    RESUME = "resume"
    OTP_CHALLENGE = "otp_challenge"


class CandidateAccessAuthMethod(str, Enum):
    TELEGRAM_INIT_DATA = "telegram_init_data"
    MAX_INIT_DATA = "max_init_data"
    SIGNED_LINK = "signed_link"
    OTP = "otp"
    ADMIN_INVITE = "admin_invite"


class CandidateLaunchChannel(str, Enum):
    TELEGRAM = "telegram"
    MAX = "max"
    SMS = "sms"
    EMAIL = "email"
    MANUAL = "manual"
    HH = "hh"


class CandidateAccessTokenPhoneVerificationState(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


class CandidateAccessSessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    BLOCKED = "blocked"


class CandidateAccessSessionPhoneVerificationState(str, Enum):
    REQUIRED = "required"
    PENDING = "pending"
    VERIFIED = "verified"
    BYPASSED = "bypassed"
    EXPIRED = "expired"


class CandidateJourneySession(Base):
    __tablename__ = "candidate_journey_sessions"
    __table_args__ = (
        Index("ix_candidate_journey_sessions_candidate_status", "candidate_id", "status"),
        Index("ix_candidate_journey_sessions_application_status", "application_id", "status"),
        Index("ix_candidate_journey_sessions_last_access_session", "last_access_session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    journey_key: Mapped[str] = mapped_column(String(64), nullable=False, default="candidate_portal")
    journey_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    entry_channel: Mapped[str] = mapped_column(String(32), nullable=False, default="web")
    current_step_key: Mapped[str] = mapped_column(String(64), nullable=False, default="profile")
    application_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_access_session_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey(
            "candidate_access_sessions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_candidate_journey_sessions_last_access_session_id",
        ),
        nullable=True,
    )
    last_surface: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_auth_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CandidateJourneySessionStatus.ACTIVE.value)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User")
    step_states: Mapped[List["CandidateJourneyStepState"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return (
            f"<CandidateJourneySession {self.id} candidate={self.candidate_id} "
            f"step={self.current_step_key} status={self.status}>"
        )


class CandidateAccessToken(Base):
    __tablename__ = "candidate_access_tokens"
    __table_args__ = (
        UniqueConstraint("token_id", name="uq_candidate_access_tokens_token_id"),
        UniqueConstraint("token_hash", name="uq_candidate_access_tokens_token_hash"),
        Index(
            "ix_candidate_access_tokens_candidate_token_kind_expires",
            "candidate_id",
            "token_kind",
            "expires_at",
        ),
        Index(
            "ix_candidate_access_tokens_application_token_kind_expires",
            "application_id",
            "token_kind",
            "expires_at",
        ),
        Index(
            "ix_candidate_access_tokens_journey_session_token_kind",
            "journey_session_id",
            "token_kind",
        ),
        Index(
            "ix_candidate_access_tokens_launch_channel_auth_created",
            "launch_channel",
            "auth_method",
            "created_at",
        ),
        Index(
            "uq_candidate_access_tokens_start_param",
            "start_param",
            unique=True,
            sqlite_where=text("start_param IS NOT NULL"),
            postgresql_where=text("start_param IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )
    journey_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("candidate_journey_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    token_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    journey_surface: Mapped[str] = mapped_column(String(24), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(24), nullable=False)
    launch_channel: Mapped[str] = mapped_column(String(16), nullable=False)
    launch_payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    start_param: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    provider_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    provider_chat_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    session_version_snapshot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    phone_verification_state: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    phone_delivery_channel: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    secret_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    issued_by_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    issued_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return (
            f"<CandidateAccessToken {self.id} kind={self.token_kind} candidate={self.candidate_id}>"
        )


class CandidateAccessSession(Base):
    __tablename__ = "candidate_access_sessions"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_candidate_access_sessions_session_id"),
        Index(
            "ix_candidate_access_sessions_candidate_status_expires",
            "candidate_id",
            "status",
            "expires_at",
        ),
        Index(
            "ix_candidate_access_sessions_application_status_expires",
            "application_id",
            "status",
            "expires_at",
        ),
        Index("ix_candidate_access_sessions_journey_status", "journey_session_id", "status"),
        Index(
            "ix_candidate_access_sessions_provider_surface_issued",
            "provider_user_id",
            "journey_surface",
            "issued_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )
    journey_session_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_journey_sessions.id"),
        nullable=False,
    )
    origin_token_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("candidate_access_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    journey_surface: Mapped[str] = mapped_column(String(24), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(24), nullable=False)
    launch_channel: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    session_version_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    phone_verification_state: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    phone_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    phone_delivery_channel: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    csrf_nonce: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CandidateAccessSessionStatus.ACTIVE.value
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return (
            f"<CandidateAccessSession {self.id} candidate={self.candidate_id} "
            f"surface={self.journey_surface} status={self.status}>"
        )


class CandidateJourneyStepState(Base):
    __tablename__ = "candidate_journey_step_states"
    __table_args__ = (
        UniqueConstraint("session_id", "step_key", name="uq_candidate_journey_step_session_key"),
        Index("ix_candidate_journey_step_states_session_status", "session_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_journey_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False, default="form")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CandidateJourneyStepStatus.PENDING.value)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
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
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["CandidateJourneySession"] = relationship(back_populates="step_states")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return (
            f"<CandidateJourneyStepState {self.id} session={self.session_id} "
            f"step={self.step_key} status={self.status}>"
        )
