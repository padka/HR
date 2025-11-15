from datetime import datetime, timezone, date
from typing import Optional, List
import html

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
    JSON,
    Table,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from markupsafe import Markup

from .base import Base


recruiter_city_association = Table(
    "recruiter_cities",
    Base.metadata,
    Column("recruiter_id", Integer, ForeignKey("recruiters.id", ondelete="CASCADE"), primary_key=True),
    Column("city_id", Integer, ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("city_id", name="uq_recruiter_city_unique_city"),
)
from backend.core.sanitizers import sanitize_plain_text


class Recruiter(Base):
    __tablename__ = "recruiters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    tg_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    tz: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    telemost_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    slots: Mapped[List["Slot"]] = relationship(back_populates="recruiter", cascade="all, delete-orphan")
    cities: Mapped[List["City"]] = relationship(
        secondary=lambda: recruiter_city_association,
        back_populates="recruiters",
    )

    def __repr__(self) -> str:
        return f"<Recruiter {self.id} {self.name}>"


class City(Base):
    __tablename__ = "cities"
    __table_args__ = (UniqueConstraint("name", name="uq_city_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tz: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    experts: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    plan_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    templates: Mapped[List["Template"]] = relationship(back_populates="city", cascade="all, delete-orphan")
    slots: Mapped[List["Slot"]] = relationship(back_populates="city", foreign_keys="Slot.city_id")
    recruiters: Mapped[List["Recruiter"]] = relationship(
        secondary=lambda: recruiter_city_association,
        back_populates="cities",
    )

    @validates("name")
    def _sanitize_name(self, _key, value: Optional[str]) -> str:
        sanitized = sanitize_plain_text(value)
        if not sanitized:
            raise ValueError("City name cannot be empty")
        return sanitized

    @property
    def name_plain(self) -> str:
        """Return the original (unescaped) city name for non-HTML contexts."""
        return html.unescape(self.name or "")

    @property
    def display_name(self) -> Markup:
        """Return a Markup-safe representation for HTML rendering."""
        return Markup(sanitize_plain_text(self.name_plain))

    def __repr__(self) -> str:
        return f"<City {self.name} ({self.tz})>"


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (UniqueConstraint("city_id", "key", name="uq_city_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cities.id", ondelete="CASCADE"), nullable=True
    )
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    city: Mapped["City"] = relationship(back_populates="templates")

    def __repr__(self) -> str:
        return f"<Template {self.key} city={self.city_id}>"


class SlotStatus:
    FREE = "free"
    PENDING = "pending"
    BOOKED = "booked"
    CONFIRMED_BY_CANDIDATE = "confirmed_by_candidate"
    CANCELED = "canceled"


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("recruiters.id", ondelete="CASCADE"))
    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id", ondelete="SET NULL"), nullable=True)
    candidate_city_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cities.id", ondelete="SET NULL"), nullable=True
    )
    purpose: Mapped[str] = mapped_column(String(32), default="interview", nullable=False)
    tz_name: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)

    start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    status: Mapped[str] = mapped_column(String(32), default=SlotStatus.FREE, nullable=False)

    candidate_tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    candidate_fio: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    candidate_tz: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    interview_outcome: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    test2_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    intro_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intro_contact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    recruiter: Mapped["Recruiter"] = relationship(back_populates="slots")
    city: Mapped[Optional["City"]] = relationship(back_populates="slots", foreign_keys=[city_id])

    def __repr__(self) -> str:
        return f"<Slot {self.id} {self.start_utc.isoformat()} {self.status}>"

    @validates("status")
    def _normalize_status(self, _key, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        raw_value = value.value if hasattr(value, "value") else value
        return str(raw_value).strip().lower()


class SlotReservationLock(Base):
    __tablename__ = "slot_reservation_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="CASCADE"), nullable=False)
    candidate_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("recruiters.id", ondelete="CASCADE"), nullable=False)
    reservation_date: Mapped[date] = mapped_column(Date, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class SlotReminderJob(Base):
    __tablename__ = "slot_reminder_jobs"
    __table_args__ = (
        UniqueConstraint("slot_id", "kind", name="uq_slot_reminder_slot_kind"),
        UniqueConstraint("job_id", name="uq_slot_reminder_job"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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


class TestQuestion(Base):
    __tablename__ = "test_questions"
    __table_args__ = (
        UniqueConstraint("test_id", "question_index", name="uq_test_question_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[str] = mapped_column(String(50), nullable=False)
    question_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<TestQuestion {self.test_id}#{self.question_index} active={self.is_active}>"


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    __table_args__ = (
        Index(
            "uq_notif_type_booking_candidate",
            "type",
            "booking_id",
            "candidate_tg_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("slots.id", ondelete="CASCADE"), nullable=False
    )
    candidate_tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delivery_status: Mapped[str] = mapped_column(
        "status", String(20), default="sent", nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    template_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    template_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class BotMessageLog(Base):
    __tablename__ = "bot_message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)
    slot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class TelegramCallbackLog(Base):
    __tablename__ = "telegram_callback_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    callback_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class MessageTemplate(Base):
    __tablename__ = "message_templates"
    __table_args__ = (
        UniqueConstraint(
            "key", "locale", "channel", "version", name="uq_template_key_locale_channel_version"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="ru")
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="tg")
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<MessageTemplate {self.key} v{self.version} locale={self.locale}>"


class OutboxNotification(Base):
    __tablename__ = "outbox_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("slots.id", ondelete="CASCADE"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    candidate_tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    recruiter_tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<OutboxNotification {self.type} booking={self.booking_id} status={self.status}>"


class ManualSlotAuditLog(Base):
    """Audit log for manually assigned slots via admin UI."""
    __tablename__ = "manual_slot_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="CASCADE"), nullable=False)
    candidate_tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("recruiters.id", ondelete="CASCADE"), nullable=False)
    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id", ondelete="SET NULL"), nullable=True)

    # What was assigned
    slot_datetime_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_tz: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), default="interview", nullable=False)

    # Custom message if sent
    custom_message_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    custom_message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit metadata
    admin_username: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Candidate state at time of assignment
    candidate_previous_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ManualSlotAuditLog slot={self.slot_id} candidate={self.candidate_tg_id} by={self.admin_username}>"
