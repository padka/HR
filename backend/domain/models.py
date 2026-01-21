from datetime import datetime, timezone, date, timedelta
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
    event,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates, object_session, reconstructor
from markupsafe import Markup

from .base import Base

# Slot duration constraints and defaults (in minutes)
DEFAULT_INTERVIEW_DURATION_MIN = 10  # Standard interview length
DEFAULT_INTRO_DAY_DURATION_MIN = 60  # Intro day slots remain 1 hour by default
SLOT_MIN_DURATION_MIN = 10  # Minimum 10 minutes
SLOT_MAX_DURATION_MIN = 240  # Maximum 4 hours


_TIMEZONE_ALIASES = {
    "europe/tomsk": "Asia/Tomsk",
}


def validate_timezone_name(tz_name: Optional[str]) -> str:
    """Validate and normalize timezone name.

    Args:
        tz_name: IANA timezone name to validate

    Returns:
        Validated timezone name

    Raises:
        ValueError: If timezone is invalid
    """
    if tz_name is None:
        raise ValueError("Timezone cannot be empty")
    cleaned = tz_name.strip()
    if not cleaned:
        raise ValueError("Timezone cannot be empty")
    alias = _TIMEZONE_ALIASES.get(cleaned.lower())
    if alias:
        cleaned = alias

    # Import here to avoid circular dependency
    from backend.core.timezone_service import TimezoneService

    if not TimezoneService.validate_timezone(cleaned):
        raise ValueError(f"Invalid timezone: {cleaned}")

    return cleaned


def validate_slot_duration(duration_min: Optional[int]) -> int:
    """Validate slot duration.

    Args:
        duration_min: Duration in minutes

    Returns:
        Validated duration

    Raises:
        ValueError: If duration is out of range
    """
    if duration_min is None:
        raise ValueError("Duration cannot be None")

    if not isinstance(duration_min, int) or duration_min <= 0:
        raise ValueError(f"Duration must be a positive integer, got: {duration_min}")

    if duration_min < SLOT_MIN_DURATION_MIN:
        raise ValueError(
            f"Slot duration too short: {duration_min} minutes. "
            f"Minimum allowed: {SLOT_MIN_DURATION_MIN} minutes"
        )

    if duration_min > SLOT_MAX_DURATION_MIN:
        raise ValueError(
            f"Slot duration too long: {duration_min} minutes. "
            f"Maximum allowed: {SLOT_MAX_DURATION_MIN} minutes ({SLOT_MAX_DURATION_MIN // 60} hours)"
        )

    return duration_min


recruiter_city_association = Table(
    "recruiter_cities",
    Base.metadata,
    Column("recruiter_id", Integer, ForeignKey("recruiters.id", ondelete="CASCADE"), primary_key=True),
    Column("city_id", Integer, ForeignKey("cities.id", ondelete="CASCADE"), primary_key=True),
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

    @validates("tz")
    def _validate_timezone(self, _key, value: Optional[str]) -> str:
        return validate_timezone_name(value)

    def __repr__(self) -> str:
        return f"<Recruiter {self.id} {self.name}>"


class City(Base):
    __tablename__ = "cities"
    __table_args__ = (UniqueConstraint("name", name="uq_city_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tz: Mapped[Optional[str]] = mapped_column(String(64), default="Europe/Moscow", nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    experts: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    plan_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    responsible_recruiter_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("recruiters.id", ondelete="SET NULL"),
        nullable=True,
    )

    templates: Mapped[List["Template"]] = relationship(back_populates="city", cascade="all, delete-orphan")
    message_templates: Mapped[List["MessageTemplate"]] = relationship(
        back_populates="city", cascade="all, delete-orphan"
    )
    slots: Mapped[List["Slot"]] = relationship(back_populates="city", foreign_keys="Slot.city_id")
    recruiters: Mapped[List["Recruiter"]] = relationship(
        secondary=lambda: recruiter_city_association,
        back_populates="cities",
    )
    responsible_recruiter: Mapped[Optional["Recruiter"]] = relationship(
        "Recruiter",
        foreign_keys=[responsible_recruiter_id],
    )

    @validates("name")
    def _sanitize_name(self, _key, value: Optional[str]) -> str:
        sanitized = sanitize_plain_text(value)
        if not sanitized:
            raise ValueError("City name cannot be empty")
        return sanitized

    @validates("tz")
    def _validate_timezone(self, _key, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return validate_timezone_name(value)

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


@event.listens_for(Recruiter.cities, "append")
def _set_city_owner(recruiter: Recruiter, city: City, _initiator) -> None:
    if city.responsible_recruiter_id in (None, recruiter.id):
        # Assign relationship to ensure FK is populated even before recruiter.id is persisted
        city.responsible_recruiter = recruiter


@event.listens_for(Recruiter.cities, "remove")
def _clear_city_owner(recruiter: Recruiter, city: City, _initiator) -> None:
    if city.responsible_recruiter_id == recruiter.id:
        city.responsible_recruiter_id = None


class SlotStatus:
    FREE = "free"
    PENDING = "pending"
    BOOKED = "booked"
    CONFIRMED = "confirmed"
    CONFIRMED_BY_CANDIDATE = "confirmed_by_candidate"  # legacy alias
    CANCELED = "canceled"
    CANCELLED = CANCELED  # spelling alias


class SlotStatusTransitionError(ValueError):
    """Raised when an invalid slot status transition is requested."""


def normalize_slot_status(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = value.value if hasattr(value, "value") else value
    return str(raw).strip().lower()


def enforce_slot_transition(current: Optional[str], target: str) -> str:
    """Validate slot status transition and return normalized target.

    Allowed forward flow: FREE -> PENDING -> BOOKED -> CONFIRMED -> CANCELED.
    Also allowed: freeing pending/booked/confirmed back to FREE (reschedule/cancel),
    idempotent transitions to the same status, and cancellation from PENDING/BOOKED/CONFIRMED.
    """
    curr = normalize_slot_status(current)
    tgt = normalize_slot_status(target)
    if tgt is None:
        raise SlotStatusTransitionError("Target status is required")

    if curr == tgt:
        return tgt

    allowed = {
        SlotStatus.FREE: {SlotStatus.PENDING},
        SlotStatus.PENDING: {SlotStatus.BOOKED, SlotStatus.FREE, SlotStatus.CANCELED},
        SlotStatus.BOOKED: {SlotStatus.CONFIRMED, SlotStatus.FREE, SlotStatus.CANCELED},
        SlotStatus.CONFIRMED: {SlotStatus.CANCELED, SlotStatus.FREE},
        SlotStatus.CONFIRMED_BY_CANDIDATE: {SlotStatus.CANCELED, SlotStatus.FREE},
        SlotStatus.CANCELED: set(),  # terminal; must recreate slot to reuse
    }

    if curr not in allowed:
        # unknown/legacy status: forbid transition to avoid silent corruption
        raise SlotStatusTransitionError(f"Unknown current status '{curr}'")

    if tgt not in allowed[curr]:
        raise SlotStatusTransitionError(f"Invalid slot status transition {curr!r} -> {tgt!r}")

    return tgt


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
    duration_min: Mapped[int] = mapped_column(Integer, default=DEFAULT_INTERVIEW_DURATION_MIN, nullable=False)

    status: Mapped[str] = mapped_column(String(32), default=SlotStatus.FREE, nullable=False)

    candidate_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.candidate_id", ondelete="SET NULL"), nullable=True
    )
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

    @reconstructor
    def _attach_timezone(self) -> None:
        """Ensure start_utc keeps UTC tzinfo when drivers (e.g. SQLite) drop it."""
        if self.start_utc is not None and self.start_utc.tzinfo is None:
            self.start_utc = self.start_utc.replace(tzinfo=timezone.utc)

    @validates("status")
    def _normalize_status(self, _key, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        raw_value = value.value if hasattr(value, "value") else value
        return str(raw_value).strip().lower()

    @validates("tz_name")
    def _validate_slot_timezone(self, _key, value: Optional[str]) -> str:
        return validate_timezone_name(value)

    @validates("candidate_tz")
    def _validate_candidate_timezone(self, _key, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return validate_timezone_name(value)

    @validates("duration_min")
    def _validate_duration(self, _key, value: Optional[int]) -> int:
        if value is None:
            raise ValueError("Duration cannot be None")
        try:
            duration = int(value)
        except (TypeError, ValueError):
            raise ValueError("Duration must be a positive integer")
        if duration <= 0:
            raise ValueError("Duration must be a positive integer")
        if duration < SLOT_MIN_DURATION_MIN:
            raise ValueError("duration too short")
        if duration > SLOT_MAX_DURATION_MIN:
            raise ValueError("duration too long")
        return duration


def _normalize_slot_start(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@event.listens_for(Slot, "before_insert")
def _enforce_slot_overlap(mapper, connection, target: Slot) -> None:  # pragma: no cover - defensive for sqlite
    """
    SQLite не поддерживает exclusion constraints, поэтому проверяем пересечения вручную.
    Повторяет поведение slots_no_recruiter_time_overlap_excl: фиксированное окно 10 минут.
    """
    if connection.dialect.name != "sqlite":
        return

    if target.recruiter_id is None:
        return

    new_start = _normalize_slot_start(target.start_utc)
    if new_start is None:
        return

    new_duration = max(target.duration_min or SLOT_MIN_DURATION_MIN, SLOT_MIN_DURATION_MIN)
    new_end = new_start + timedelta(minutes=new_duration)

    existing_rows = connection.execute(
        select(Slot.start_utc, Slot.duration_min).where(Slot.recruiter_id == target.recruiter_id)
    )
    for row in existing_rows:
        start_raw, duration_raw = (row.start_utc, row.duration_min) if hasattr(row, "start_utc") else row
        existing = _normalize_slot_start(start_raw)
        if existing is None:
            continue
        existing_duration = max(duration_raw or SLOT_MIN_DURATION_MIN, SLOT_MIN_DURATION_MIN)
        existing_end = existing + timedelta(minutes=existing_duration)
        if new_start < existing_end and new_end > existing:
            from sqlalchemy.exc import IntegrityError

            raise IntegrityError("slots_no_recruiter_time_overlap_excl", params=None, orig=Exception("slot_overlap"))

    @validates("duration_min")
    def _validate_duration(self, _key, value: Optional[int]) -> int:
        return validate_slot_duration(value)


class SlotReservationLock(Base):
    __tablename__ = "slot_reservation_locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    candidate_tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
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
            "key",
            "locale",
            "channel",
            "city_id",
            "version",
            name="uq_template_key_locale_channel_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="ru")
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="tg")
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    city_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cities.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    city: Mapped[Optional["City"]] = relationship(back_populates="message_templates")

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<MessageTemplate {self.key} v{self.version} locale={self.locale}>"


class MessageTemplateHistory(Base):
    __tablename__ = "message_template_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("message_templates.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="ru")
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="tg")
    city_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cities.id", ondelete="SET NULL"), nullable=True
    )
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    city: Mapped[Optional["City"]] = relationship()
    template: Mapped["MessageTemplate"] = relationship()


class KPIWeekly(Base):
    """Aggregated weekly KPIs for the candidate funnel."""

    __tablename__ = "kpi_weekly"

    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    tested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_test: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    booked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interview_passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intro_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return (
            f"<KPIWeekly week_start={self.week_start} "
            f"tested={self.tested} booked={self.booked} intro_day={self.intro_day}>"
        )


class OutboxNotification(Base):
    __tablename__ = "outbox_notifications"
    __table_args__ = (
        Index("ix_outbox_status_created", "status", "created_at"),
        Index(
            "ix_outbox_status_retry",
            "status",
            "next_retry_at",
            postgresql_where="next_retry_at IS NOT NULL",
        ),
        Index(
            "ix_outbox_correlation",
            "correlation_id",
            postgresql_where="correlation_id IS NOT NULL",
        ),
    )

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


class AuditLog(Base):
    """Generic audit log for admin actions."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    changes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"<AuditLog action={self.action} entity={self.entity_type}:{self.entity_id}>"
