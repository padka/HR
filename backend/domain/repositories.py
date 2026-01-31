import html
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased, selectinload
from dataclasses import dataclass
from typing import Literal


from backend.core.db import async_session
from backend.core.sanitizers import sanitize_plain_text
from backend.domain.candidates.services import create_or_update_user
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus

_UNSET = object()

from .models import (
    City,
    MessageTemplate,
    NotificationLog,
    BotMessageLog,
    MessageLog,
    OutboxNotification,
    Recruiter,
    Slot,
    SlotReservationLock,
    SlotStatus,
    TelegramCallbackLog,
    Template,
    recruiter_city_association,
)

logger = logging.getLogger(__name__)


def slot_status_free_clause(slot: Slot):
    """Return a SQLAlchemy expression matching free slots (shared across UI/API)."""
    return func.lower(slot.status) == SlotStatus.FREE


def slot_status_free_sql(alias: str = "s") -> str:
    """Return SQL snippet to filter free slots for raw text queries."""
    return f"lower(coalesce({alias}.status, 'free')) = '{SlotStatus.FREE}'"

def _to_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def get_active_recruiters() -> List[Recruiter]:
    async with async_session() as session:
        res = await session.scalars(
            select(Recruiter).where(Recruiter.active.is_(True)).order_by(Recruiter.name.asc())
        )
        return list(res)


async def get_active_recruiters_for_city(city_id: int) -> List[Recruiter]:
    """Return recruiters that can process candidates from the given city.

    A recruiter may be linked to the city explicitly (as the responsible
    recruiter configured in the admin UI) or implicitly by owning free slots
    for the city. The second case is important because slot management lives in
    the admin interface: recruiters can be scheduled for specific cities
    without being marked as the responsible contact. The bot must therefore be
    aware of both kinds of relationships to present an accurate choice to the
    candidate after Test 1.
    """

    now = datetime.now(timezone.utc)

    rc = recruiter_city_association.alias("rc")
    city_alias = aliased(City)

    async with async_session() as session:
        res = await session.scalars(
            select(Recruiter)
            .outerjoin(
                rc,
                and_(
                    rc.c.recruiter_id == Recruiter.id,
                    rc.c.city_id == city_id,
                ),
            )
            .outerjoin(
                city_alias,
                and_(city_alias.id == rc.c.city_id, city_alias.active.is_(True)),
            )
            .outerjoin(
                Slot,
                and_(
                    Slot.recruiter_id == Recruiter.id,
                    Slot.city_id == city_id,
                    slot_status_free_clause(Slot),
                    Slot.start_utc > now,
                ),
            )
            .where(
                Recruiter.active.is_(True),
                or_(city_alias.id == city_id, Slot.id.is_not(None)),
            )
            .group_by(Recruiter.id)
            .order_by(Recruiter.name.asc())
        )
        return list(res)


async def get_candidate_cities() -> List[City]:
    """Return active cities for the bot city picker.

    We still compute "available" cities (with responsible recruiters or future
    free slots) but return the full active list so candidates can select any
    city configured in the system. Available cities are sorted first.
    """

    now = datetime.now(timezone.utc)

    rc = recruiter_city_association.alias("rc")
    responsible = aliased(Recruiter)
    slot = aliased(Slot)
    slot_owner = aliased(Recruiter)

    async with async_session() as session:
        city_query = (
            select(City)
            .outerjoin(
                rc,
                rc.c.city_id == City.id,
            )
            .outerjoin(
                responsible,
                and_(
                    responsible.id == rc.c.recruiter_id,
                    responsible.active.is_(True),
                ),
            )
            .outerjoin(
                slot,
                and_(
                    slot.city_id == City.id,
                    slot_status_free_clause(slot),
                    slot.start_utc > now,
                ),
            )
            .outerjoin(
                slot_owner,
                and_(
                    slot_owner.id == slot.recruiter_id,
                    slot_owner.active.is_(True),
                ),
            )
            .where(
                City.active.is_(True),
                or_(responsible.id.is_not(None), slot_owner.id.is_not(None)),
            )
            .group_by(City.id)
            .order_by(City.name.asc())
        )
        available = list(await session.scalars(city_query))
        available_ids = {city.id for city in available if city.id is not None}

        all_cities = list(
            await session.scalars(
                select(City).where(City.active.is_(True)).order_by(City.name.asc())
            )
        )
        if not available_ids:
            return all_cities

        # Stable sort: available cities first, then the rest (both name-ordered already).
        return [
            *[city for city in all_cities if city.id in available_ids],
            *[city for city in all_cities if city.id not in available_ids],
        ]


async def get_recruiter(recruiter_id: int) -> Optional[Recruiter]:
    async with async_session() as session:
        return await session.get(Recruiter, recruiter_id)


async def get_recruiter_by_chat_id(chat_id: int) -> Optional[Recruiter]:
    """Return recruiter record by Telegram chat id, if any."""
    async with async_session() as session:
        return await session.scalar(
            select(Recruiter).where(Recruiter.tg_chat_id == chat_id)
        )


async def get_recruiter_agenda_by_chat_id(
    chat_id: int,
    *,
    start_utc: datetime,
    end_utc: datetime,
    limit: int = 30,
) -> List[Slot]:
    """Return slots for recruiter by tg chat id within time window."""
    async with async_session() as session:
        stmt = (
            select(Slot)
            .join(Recruiter, Slot.recruiter_id == Recruiter.id)
            .where(
                and_(
                    Recruiter.tg_chat_id == chat_id,
                    Slot.start_utc >= start_utc,
                    Slot.start_utc <= end_utc,
                    Slot.status.in_(
                        [
                            SlotStatus.PENDING,
                            SlotStatus.BOOKED,
                            SlotStatus.CONFIRMED_BY_CANDIDATE,
                            SlotStatus.FREE,
                        ]
                    ),
                )
            )
            .order_by(Slot.start_utc.asc())
            .limit(limit)
        )
        rows = await session.scalars(stmt)
        return list(rows.all())


async def get_city_by_name(name: str) -> Optional[City]:
    async with async_session() as session:
        res = await session.scalars(select(City).where(City.name.ilike(name.strip())))
        return res.first()


_CITY_PREFIX_RE = re.compile(r"^(город|гор\.?|г\.?)\s+", re.IGNORECASE)
_CITY_SPLIT_SEPARATORS = [",", "/", "(", ")", "—", "-", ";", "|"]


def _normalize_city_part(value: str) -> str:
    candidate = sanitize_plain_text(value)
    plain = html.unescape(candidate or "").strip()
    if not plain:
        return ""
    plain = _CITY_PREFIX_RE.sub("", plain).strip()
    plain = plain.replace("ё", "е")
    plain = re.sub(r"[^\w\s-]", " ", plain, flags=re.UNICODE)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain.casefold()


def _city_variants(value: Optional[str]) -> List[str]:
    if not value:
        return []
    parts = {value}
    for sep in _CITY_SPLIT_SEPARATORS:
        for chunk in value.split(sep):
            parts.add(chunk.strip())
    normalized = []
    for part in parts:
        norm = _normalize_city_part(part)
        if norm:
            normalized.append(norm)
    return normalized


async def find_city_by_plain_name(name: Optional[str]) -> Optional[City]:
    """Case-insensitive lookup tolerant к приставкам (“г.”) и составным названиям."""

    candidates = _city_variants(name)
    if not candidates:
        return None

    async with async_session() as session:
        result = await session.execute(select(City.id, City.name))
        match_city_id: Optional[int] = None
        for city_id, stored_name in result:
            stored_plain = html.unescape(stored_name or "")
            stored_variants = _city_variants(stored_plain)
            if any(candidate in stored_variants for candidate in candidates):
                match_city_id = city_id
                break
        if match_city_id is None:
            return None
        return await session.get(City, match_city_id)


async def city_has_available_slots(city_id: int, *, now_utc: Optional[datetime] = None) -> bool:
    """Return True if there is at least one free future slot for the city."""

    now_utc = now_utc or datetime.now(timezone.utc)
    async with async_session() as session:
        total = await session.scalar(
            select(func.count())
            .select_from(Slot)
            .where(
                Slot.city_id == city_id,
                # Only interview slots count for availability
                func.coalesce(Slot.purpose, "interview") == "interview",
                func.lower(Slot.status) == SlotStatus.FREE,
                Slot.start_utc > now_utc,
            )
        )
        return bool(total)


async def get_city(city_id: int) -> Optional[City]:
    async with async_session() as session:
        result = await session.execute(
            select(City)
            .options(selectinload(City.recruiters))
            .where(City.id == city_id)
        )
        return result.scalar_one_or_none()


async def get_free_slots_by_recruiter(
    recruiter_id: int,
    now_utc: Optional[datetime] = None,
    *,
    city_id: Optional[int] = None,
) -> List[Slot]:
    now_utc = now_utc or datetime.now(timezone.utc)
    async with async_session() as session:
        query = (
            select(Slot)
            .where(
                Slot.recruiter_id == recruiter_id,
                func.lower(Slot.status) == SlotStatus.FREE,
                Slot.start_utc > now_utc,
            )
            .order_by(Slot.start_utc.asc())
        )
        if city_id is not None:
            query = query.where(Slot.city_id == city_id)

        res = await session.scalars(query)
        out = list(res)
        for slot in out:
            slot.start_utc = _to_aware_utc(slot.start_utc)
        return out


async def get_recruiters_free_slots_summary(
    recruiter_ids: Iterable[int],
    now_utc: Optional[datetime] = None,
    *,
    city_id: Optional[int] = None,
) -> Dict[int, Tuple[datetime, int]]:
    ids = {int(rid) for rid in recruiter_ids if rid is not None}
    if not ids:
        return {}

    now_utc = now_utc or datetime.now(timezone.utc)

    async with async_session() as session:
        rows = (
            await session.execute(
                select(
                    Slot.recruiter_id,
                    func.min(Slot.start_utc).label("next_start"),
                    func.count(Slot.id).label("total_slots"),
                )
                .where(
                    Slot.recruiter_id.in_(ids),
                    func.lower(Slot.status) == SlotStatus.FREE,
                    Slot.start_utc > now_utc,
                    *(
                        [Slot.city_id == city_id]
                        if city_id is not None
                        else []
                    ),
                )
                .group_by(Slot.recruiter_id)
            )
        ).all()

    summary: Dict[int, Tuple[datetime, int]] = {}
    for recruiter_id, next_start, total in rows:
        if next_start is None:
            continue
        summary[int(recruiter_id)] = (_to_aware_utc(next_start), int(total))
    return summary


async def get_slot(slot_id: int) -> Optional[Slot]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if slot:
            slot.start_utc = _to_aware_utc(slot.start_utc)
        return slot


async def get_template(city_id: Optional[int], key: str) -> Optional[Template]:
    async with async_session() as session:
        base = select(Template).where(Template.key == key)
        if city_id is None:
            res = await session.scalars(base.where(Template.city_id.is_(None)))
            return res.first()

        res = await session.scalars(base.where(Template.city_id == city_id))
        tmpl = res.first()
        if tmpl:
            return tmpl
        fallback = await session.scalars(base.where(Template.city_id.is_(None)))
        return fallback.first()


async def get_message_template(
    key: str,
    *,
    locale: str = "ru",
    channel: str = "tg",
    city_id: Optional[int] = None,
) -> Optional[MessageTemplate]:
    async with async_session() as session:
        base = (
            select(MessageTemplate)
            .where(
                MessageTemplate.key == key,
                MessageTemplate.locale == locale,
                MessageTemplate.channel == channel,
                MessageTemplate.is_active.is_(True),
            )
            .order_by(MessageTemplate.version.desc(), MessageTemplate.updated_at.desc())
            .limit(1)
        )

        queries = []
        if city_id is not None:
            queries.append(base.where(MessageTemplate.city_id == city_id))
        queries.append(base.where(MessageTemplate.city_id.is_(None)))

        for query in queries:
            result = await session.scalars(query)
            found = result.first()
            if found:
                return found
        return None


@dataclass
class ReservationResult:
    status: Literal["reserved", "slot_taken", "duplicate_candidate", "already_reserved"]
    slot: Optional[Slot] = None


@dataclass
class OutboxItem:
    """Lightweight representation of a pending outbox notification."""

    id: int
    booking_id: Optional[int]
    type: str
    payload: Dict[str, Any]
    candidate_tg_id: Optional[int]
    recruiter_tg_id: Optional[int]
    attempts: int
    created_at: datetime
    next_retry_at: Optional[datetime] = None


@dataclass
class CandidateConfirmationResult:
    status: Literal["not_found", "invalid_status", "already_confirmed", "confirmed"]
    slot: Optional[Slot] = None


async def register_callback(callback_id: str) -> bool:
    if not callback_id:
        return True

    async with async_session() as session:
        async with session.begin():
            exists = await session.scalar(
                select(TelegramCallbackLog.id)
                .where(TelegramCallbackLog.callback_id == callback_id)
                .with_for_update()
            )
            if exists:
                return False
            session.add(
                TelegramCallbackLog(
                    callback_id=callback_id,
                    created_at=datetime.now(timezone.utc),
                )
            )
    return True


def _log_candidate_clause(candidate_tg_id: Optional[int]):
    if candidate_tg_id is None:
        return NotificationLog.candidate_tg_id.is_(None)
    return NotificationLog.candidate_tg_id == candidate_tg_id


def _outbox_candidate_clause(candidate_tg_id: Optional[int]):
    if candidate_tg_id is None:
        return OutboxNotification.candidate_tg_id.is_(None)
    return OutboxNotification.candidate_tg_id == candidate_tg_id


async def notification_log_exists(
    notification_type: str,
    booking_id: int,
    *,
    candidate_tg_id: Optional[int] = None,
) -> bool:
    async with async_session() as session:
        if candidate_tg_id is None:
            candidate_tg_id = await session.scalar(
                select(Slot.candidate_tg_id).where(Slot.id == booking_id)
            )
        existing = await session.scalar(
            select(NotificationLog.id).where(
                NotificationLog.type == notification_type,
                NotificationLog.booking_id == booking_id,
                _log_candidate_clause(candidate_tg_id),
            )
        )
        return existing is not None


async def get_notification_log(
    notification_type: str,
    booking_id: int,
    *,
    candidate_tg_id: Optional[int] = None,
    for_update: bool = False,
) -> Optional[NotificationLog]:
    async with async_session() as session:
        if candidate_tg_id is None:
            candidate_tg_id = await session.scalar(
                select(Slot.candidate_tg_id).where(Slot.id == booking_id)
            )
        query = select(NotificationLog).where(
            NotificationLog.type == notification_type,
            NotificationLog.booking_id == booking_id,
            _log_candidate_clause(candidate_tg_id),
        )
        if for_update:
            query = query.with_for_update()
        return await session.scalar(query)


async def get_notification_log_by_id(
    log_id: int,
    *,
    for_update: bool = False,
) -> Optional[NotificationLog]:
    async with async_session() as session:
        query = select(NotificationLog).where(NotificationLog.id == log_id)
        if for_update:
            query = query.with_for_update()
        return await session.scalar(query)


async def add_notification_log(
    notification_type: str,
    booking_id: int,
    *,
    candidate_tg_id: Optional[int] = None,
    payload: Optional[str] = None,
    delivery_status: str = "sent",
    attempts: int = 1,
    last_error: Optional[str] = None,
    next_retry_at: Optional[datetime] = None,
    overwrite: bool = False,
    template_key: Optional[str] = None,
    template_version: Optional[int] = None,
) -> bool:
    async with async_session() as session:
        async with session.begin():
            if candidate_tg_id is None:
                candidate_tg_id = await session.scalar(
                    select(Slot.candidate_tg_id).where(Slot.id == booking_id)
                )
            values = {
                "booking_id": booking_id,
                "candidate_tg_id": candidate_tg_id,
                "type": notification_type,
                "payload": payload,
                "delivery_status": delivery_status,
                "attempts": attempts,
                "last_error": last_error,
                "next_retry_at": next_retry_at,
                "template_key": template_key,
                "template_version": template_version,
                "created_at": datetime.now(timezone.utc),
            }
            bind = session.get_bind()
            dialect_name = bind.dialect.name if bind is not None else ""

            if dialect_name in {"sqlite", "postgresql"}:
                insert_factory = sqlite_insert if dialect_name == "sqlite" else pg_insert
                stmt = (
                    insert_factory(NotificationLog)
                    .values(**values)
                    # SQLite enforces unique constraints per-table; on_conflict_do_nothing()
                    # without index_elements works across all constraints and prevents crashes
                    # when different backends use different constraint names/columns.
                    .on_conflict_do_nothing()
                )
                result = await session.execute(stmt)
                inserted = result.rowcount == 1
                if inserted or not overwrite:
                    return inserted

                update_stmt = (
                    update(NotificationLog)
                    .where(
                        NotificationLog.type == notification_type,
                        NotificationLog.booking_id == booking_id,
                        _log_candidate_clause(candidate_tg_id),
                    )
                    .values(
                        payload=payload,
                        delivery_status=delivery_status,
                        attempts=attempts,
                        last_error=last_error,
                        next_retry_at=next_retry_at,
                        template_key=template_key,
                        template_version=template_version,
                    )
                )
                await session.execute(update_stmt)
                return False

            existing = await session.scalar(
                select(NotificationLog)
                .where(
                    NotificationLog.type == notification_type,
                    NotificationLog.booking_id == booking_id,
                    _log_candidate_clause(candidate_tg_id),
                )
                .with_for_update()
            )
            if existing:
                if overwrite:
                    existing.payload = payload
                    existing.delivery_status = delivery_status
                    existing.attempts = attempts
                    existing.last_error = last_error
                    existing.next_retry_at = next_retry_at
                    existing.template_key = template_key
                    existing.template_version = template_version
                return False

            session.add(NotificationLog(**values))
            return True


async def add_bot_message_log(
    message_type: str,
    *,
    candidate_tg_id: Optional[int] = None,
    slot_id: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    async with async_session() as session:
        session.add(
            BotMessageLog(
                message_type=message_type,
                candidate_tg_id=candidate_tg_id,
                slot_id=slot_id,
                payload_json=payload,
                sent_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def add_message_log(
    message_type: str,
    *,
    recipient_type: str,
    recipient_id: Optional[int] = None,
    slot_assignment_id: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    status: str = "sent",
    channel: str = "tg",
) -> None:
    async with async_session() as session:
        session.add(
            MessageLog(
                channel=channel,
                recipient_type=recipient_type,
                recipient_id=recipient_id,
                slot_assignment_id=slot_assignment_id,
                message_type=message_type,
                payload_json=payload,
                delivery_status=status,
                created_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def update_notification_log_fields(
    log_id: int,
    *,
    delivery_status: Optional[str] = None,
    payload: object = _UNSET,
    attempts: Optional[int] = None,
    last_error: object = _UNSET,
    next_retry_at: object = _UNSET,
    template_key: object = _UNSET,
    template_version: object = _UNSET,
) -> None:
    async with async_session() as session:
        async with session.begin():
            log = await session.get(NotificationLog, log_id, with_for_update=True)
            if not log:
                return
            if delivery_status is not None:
                log.delivery_status = delivery_status
            if payload is not _UNSET:
                log.payload = payload  # type: ignore[assignment]
            if attempts is not None:
                log.attempts = attempts
            if last_error is not _UNSET:
                log.last_error = last_error  # type: ignore[assignment]
            if next_retry_at is not _UNSET:
                log.next_retry_at = next_retry_at  # type: ignore[assignment]
            if template_key is not _UNSET:
                log.template_key = template_key  # type: ignore[assignment]
            if template_version is not _UNSET:
                log.template_version = template_version  # type: ignore[assignment]


async def add_outbox_notification(
    *,
    notification_type: str,
    booking_id: Optional[int],
    payload: Optional[Dict[str, Any]] = None,
    candidate_tg_id: Optional[int] = None,
    recruiter_tg_id: Optional[int] = None,
    correlation_id: Optional[str] = None,
    session=None,
) -> OutboxNotification:
    payload = payload or {}
    now = datetime.now(timezone.utc)

    async def _add(sess) -> OutboxNotification:
        # First, check if entry exists (regardless of status) to ensure idempotency
        existing = await sess.scalar(
            select(OutboxNotification)
            .where(
                OutboxNotification.type == notification_type,
                OutboxNotification.booking_id == booking_id,
                OutboxNotification.candidate_tg_id == candidate_tg_id,
            )
            .with_for_update()
        )

        if existing:
            # If status is 'pending', update it (reuse for retry)
            if existing.status == "pending":
                if recruiter_tg_id is not None:
                    existing.recruiter_tg_id = recruiter_tg_id
                if payload:
                    existing.payload_json = payload
                if correlation_id:
                    existing.correlation_id = correlation_id
                existing.next_retry_at = None
                existing.locked_at = None
                if existing.attempts > 0:
                    existing.attempts = 0
                return existing
            else:
                # Status is 'sent' or 'failed' - return as-is (idempotent)
                # Don't modify sent/failed entries to prevent duplicate messages
                return existing

        # No existing entry - create new one
        entry = OutboxNotification(
            booking_id=booking_id,
            type=notification_type,
            payload_json=payload,
            candidate_tg_id=candidate_tg_id,
            recruiter_tg_id=recruiter_tg_id,
            status="pending",
            attempts=0,
            created_at=now,
            locked_at=None,
            next_retry_at=None,
            correlation_id=correlation_id,
        )
        sess.add(entry)
        return entry

    if session is not None:
        return await _add(session)

    async with async_session() as sess:
        async with sess.begin():
            entry = await _add(sess)
        await sess.refresh(entry)
        return entry


async def claim_outbox_batch(
    *,
    batch_size: int,
    lock_timeout: timedelta = timedelta(seconds=30),
) -> List[OutboxItem]:
    now = datetime.now(timezone.utc)
    stale_before = now - lock_timeout
    async with async_session() as session:
        async with session.begin():
            # Use with_for_update(skip_locked=True) to prevent race conditions
            # between multiple workers claiming the same notifications.
            # skip_locked=True ensures we skip rows already locked by other transactions
            # rather than waiting for them.
            rows = (
                await session.execute(
                    select(OutboxNotification)
                    .where(
                        OutboxNotification.status == "pending",
                        or_(
                            OutboxNotification.next_retry_at.is_(None),
                            OutboxNotification.next_retry_at <= now,
                        ),
                        or_(
                            OutboxNotification.locked_at.is_(None),
                            OutboxNotification.locked_at <= stale_before,
                        ),
                    )
                    .order_by(OutboxNotification.id.asc())
                    .limit(batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).scalars().all()

            for row in rows:
                row.locked_at = now

            if rows:
                await session.flush()

            items: List[OutboxItem] = []
            for row in rows:
                items.append(
                    OutboxItem(
                        id=row.id,
                        booking_id=row.booking_id,
                        type=row.type,
                        payload=dict(row.payload_json or {}),
                        candidate_tg_id=row.candidate_tg_id,
                        recruiter_tg_id=row.recruiter_tg_id,
                        attempts=row.attempts,
                        created_at=row.created_at,
                        next_retry_at=row.next_retry_at,
                )
        )
        return items


async def update_outbox_entry(
    outbox_id: int,
    *,
    status: Optional[str] = None,
    attempts: Optional[int] = None,
    next_retry_at: object = _UNSET,
    last_error: object = _UNSET,
    correlation_id: Optional[str] = None,
) -> None:
    values: Dict[str, Any] = {"locked_at": None}
    if status is not None:
        values["status"] = status
    if attempts is not None:
        values["attempts"] = attempts
    if next_retry_at is not _UNSET:
        if next_retry_at is None or isinstance(next_retry_at, datetime):
            values["next_retry_at"] = next_retry_at
    if last_error is not _UNSET:
        values["last_error"] = last_error
    if correlation_id is not None:
        values["correlation_id"] = correlation_id

    async with async_session() as session:
        async with session.begin():
            await session.execute(
                update(OutboxNotification)
                .where(OutboxNotification.id == outbox_id)
                .values(values)
            )


async def mark_outbox_notification_sent(
    notification_type: str,
    booking_id: Optional[int],
    *,
    candidate_tg_id: Optional[int] = None,
) -> int:
    async with async_session() as session:
        async with session.begin():
            stmt = (
                update(OutboxNotification)
                .where(
                    OutboxNotification.type == notification_type,
                    OutboxNotification.booking_id == booking_id,
                    _outbox_candidate_clause(candidate_tg_id),
                    OutboxNotification.status == "pending",
                )
                .values(
                    status="sent",
                    locked_at=None,
                    attempts=1,
                    next_retry_at=None,
                    last_error=None,
                )
            )
            result = await session.execute(stmt)
            return int(result.rowcount or 0)


async def get_outbox_queue_depth() -> int:
    async with async_session() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(OutboxNotification)
            .where(OutboxNotification.status == "pending")
        )
        return int(count or 0)


async def get_outbox_item(outbox_id: int) -> Optional[OutboxItem]:
    async with async_session() as session:
        entry = await session.get(OutboxNotification, outbox_id)
        if entry is None:
            return None
        return OutboxItem(
            id=entry.id,
            booking_id=entry.booking_id,
            type=entry.type,
            payload=dict(entry.payload_json or {}),
            candidate_tg_id=entry.candidate_tg_id,
            recruiter_tg_id=entry.recruiter_tg_id,
            attempts=entry.attempts,
            created_at=entry.created_at,
            next_retry_at=entry.next_retry_at,
        )


async def reset_outbox_entry(outbox_id: int) -> None:
    async with async_session() as session:
        async with session.begin():
            entry = await session.get(OutboxNotification, outbox_id, with_for_update=True)
            if not entry:
                return
            entry.status = "pending"
            entry.locked_at = None
            entry.next_retry_at = None
            entry.attempts = 0
            entry.last_error = None
async def confirm_slot_by_candidate(slot_id: int) -> CandidateConfirmationResult:
    async with async_session() as session:
        try:
            async with session.begin():
                slot = await session.scalar(
                    select(Slot)
                    .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                    .where(Slot.id == slot_id)
                    .with_for_update()
                )

                if slot is None:
                    return CandidateConfirmationResult(status="not_found", slot=None)

                status_value = (slot.status or "").lower()
                if status_value == SlotStatus.CONFIRMED_BY_CANDIDATE:
                    slot.start_utc = _to_aware_utc(slot.start_utc)
                    return CandidateConfirmationResult(status="already_confirmed", slot=slot)

                if status_value not in {SlotStatus.BOOKED, SlotStatus.PENDING}:
                    slot.start_utc = _to_aware_utc(slot.start_utc)
                    return CandidateConfirmationResult(status="invalid_status", slot=slot)

                candidate_tg_id = slot.candidate_tg_id
                existing_log = await session.scalar(
                    select(NotificationLog.id)
                    .where(
                        NotificationLog.booking_id == slot_id,
                        NotificationLog.type == "candidate_confirm",
                        _log_candidate_clause(candidate_tg_id),
                    )
                    .with_for_update()
                )
                if existing_log:
                    slot.status = SlotStatus.CONFIRMED_BY_CANDIDATE
                    slot.start_utc = _to_aware_utc(slot.start_utc)
                    return CandidateConfirmationResult(status="already_confirmed", slot=slot)

                slot.status = SlotStatus.CONFIRMED_BY_CANDIDATE

                # Update candidate status depending on slot purpose
                if candidate_tg_id is not None:
                    try:
                        from backend.domain.candidates.status_service import (
                            set_status_interview_confirmed,
                            set_status_intro_day_confirmed_preliminary,
                        )

                        is_intro_day = (slot.purpose or "").lower() == "intro_day"
                        if is_intro_day:
                            await set_status_intro_day_confirmed_preliminary(candidate_tg_id, force=True)
                        else:
                            await set_status_interview_confirmed(candidate_tg_id)
                    except Exception:
                        logger.exception("Failed to update candidate status for candidate %s", candidate_tg_id)

                # Add notification log (idempotent - ignore if already exists)
                # Use no_autoflush to prevent premature flush during subsequent queries
                with session.no_autoflush:
                    session.add(
                        NotificationLog(
                            booking_id=slot.id,
                            candidate_tg_id=candidate_tg_id,
                            type="candidate_confirm",
                            created_at=datetime.now(timezone.utc),
                        )
                    )

                recruiter_tg_id = (
                    slot.recruiter.tg_chat_id if slot.recruiter and slot.recruiter.tg_chat_id else None
                )
                await add_outbox_notification(
                    notification_type="recruiter_candidate_confirmed_notice",
                    booking_id=slot.id,
                    candidate_tg_id=candidate_tg_id,
                    recruiter_tg_id=recruiter_tg_id,
                    payload={
                        "event": "candidate_confirmed",
                        "slot_id": slot.id,
                    },
                    session=session,
                )

            slot.start_utc = _to_aware_utc(slot.start_utc)
            return CandidateConfirmationResult(status="confirmed", slot=slot)
        except IntegrityError as e:
            # IntegrityError on NotificationLog unique constraint = idempotent retry
            # This means another request already confirmed this slot
            logger.info(
                "IntegrityError during confirm_slot_by_candidate for slot %s - treating as idempotent retry: %s",
                slot_id,
                str(e)
            )
            # Re-fetch slot to return current state
            async with session.begin():
                slot = await session.scalar(
                    select(Slot)
                    .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                    .where(Slot.id == slot_id)
                )
                if slot:
                    slot.start_utc = _to_aware_utc(slot.start_utc)
                    return CandidateConfirmationResult(status="already_confirmed", slot=slot)
                else:
                    return CandidateConfirmationResult(status="not_found", slot=None)


async def reserve_slot(
    slot_id: int,
    candidate_tg_id: Optional[int],
    candidate_fio: str,
    candidate_tz: str,
    *,
    candidate_id: Optional[str] = None,
    candidate_city_id: Optional[int] = None,
    candidate_username: Optional[str] = None,
    purpose: str = "interview",
    expected_recruiter_id: Optional[int] = None,
    expected_city_id: Optional[int] = None,
    allow_candidate_replace: bool = False,
) -> ReservationResult:
    """Attempt to reserve the slot and describe the outcome."""
    now_utc = datetime.now(timezone.utc)

    city_name: Optional[str] = None
    candidate_uuid: Optional[str] = None
    slot_recruiter_id: Optional[int] = None
    slot_purpose = purpose or "interview"

    async with async_session() as session:
        try:
            async with session.begin():
                candidate_uuid = candidate_id
                if candidate_uuid is None and candidate_tg_id is not None:
                    candidate_uuid = await session.scalar(
                        select(User.candidate_id).where(User.telegram_id == candidate_tg_id)
                    )
                if candidate_uuid is None:
                    candidate_uuid = f"tg:{candidate_tg_id}" if candidate_tg_id is not None else str(uuid.uuid4())

                slot = await session.scalar(
                    select(Slot)
                    .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                    .where(Slot.id == slot_id)
                    .with_for_update()
                )

                if not slot:
                    return ReservationResult(status="slot_taken")

                slot_recruiter_id = slot.recruiter_id

                status_value = (slot.status or "").lower()
                slot_purpose_value = (slot.purpose or "interview").lower()
                if slot_purpose_value != slot_purpose:
                    return ReservationResult(status="slot_taken")

                # Не позволяем бронировать слоты, которые уже в прошлом.
                slot_start = _to_aware_utc(slot.start_utc)
                if slot_start <= now_utc:
                    return ReservationResult(status="slot_taken", slot=slot)

                if status_value != SlotStatus.FREE:
                    if (
                        slot.candidate_id == candidate_uuid
                        or (candidate_tg_id is not None and slot.candidate_tg_id == candidate_tg_id)
                    ) and status_value in (
                        SlotStatus.PENDING,
                        SlotStatus.BOOKED,
                        SlotStatus.CONFIRMED_BY_CANDIDATE,
                    ):
                        slot.start_utc = _to_aware_utc(slot.start_utc)
                        return ReservationResult(status="already_reserved", slot=slot)
                    return ReservationResult(status="slot_taken", slot=slot)

                if expected_recruiter_id is not None and slot.recruiter_id != expected_recruiter_id:
                    return ReservationResult(status="slot_taken")

                if expected_city_id is not None and slot.city_id != expected_city_id:
                    return ReservationResult(status="slot_taken")

                # P0: do not allow the same candidate to hold multiple active slots WITH THE SAME RECRUITER.
                # Candidate can book different recruiters (e.g., reschedule to another recruiter).
                # If allow_candidate_replace=True, free the existing slot and continue booking.
                existing_active = await session.scalar(
                    select(Slot)
                    .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                    .where(
                        Slot.candidate_id == candidate_uuid,
                        Slot.recruiter_id == slot.recruiter_id,  # Same recruiter only
                        Slot.id != slot.id,
                        func.lower(Slot.status).in_(
                            [
                                SlotStatus.PENDING,
                                SlotStatus.BOOKED,
                                SlotStatus.CONFIRMED_BY_CANDIDATE,
                            ]
                        ),
                    )
                )
                if existing_active:
                    if allow_candidate_replace:
                        # Clean up the existing booking without changing candidate status.
                        await session.execute(
                            delete(SlotReservationLock).where(SlotReservationLock.slot_id == existing_active.id)
                        )
                        await session.execute(
                            delete(NotificationLog).where(NotificationLog.booking_id == existing_active.id)
                        )
                        existing_active.status = SlotStatus.FREE
                        existing_active.candidate_id = None
                        existing_active.candidate_tg_id = None
                        existing_active.candidate_fio = None
                        existing_active.candidate_tz = None
                        existing_active.candidate_city_id = None
                    else:
                        existing_active.start_utc = _to_aware_utc(existing_active.start_utc)
                        return ReservationResult(status="duplicate_candidate", slot=existing_active)

                reservation_date = _to_aware_utc(slot.start_utc).date()

                await session.execute(
                    delete(SlotReservationLock).where(SlotReservationLock.expires_at <= now_utc)
                )

                existing_lock = await session.scalar(
                    select(SlotReservationLock)
                    .where(
                        SlotReservationLock.candidate_id == candidate_uuid,
                        SlotReservationLock.recruiter_id == slot.recruiter_id,
                        SlotReservationLock.reservation_date == reservation_date,
                    )
                    .with_for_update()
                )

                if existing_lock:
                    existing_slot = await session.scalar(
                        select(Slot)
                        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                        .where(Slot.id == existing_lock.slot_id)
                    )
                    if existing_slot:
                        existing_slot.start_utc = _to_aware_utc(existing_slot.start_utc)
                        return ReservationResult(status="already_reserved", slot=existing_slot)
                    await session.delete(existing_lock)

                slot.status = SlotStatus.PENDING
                slot.candidate_id = candidate_uuid
                slot.candidate_tg_id = candidate_tg_id
                slot.candidate_fio = candidate_fio
                slot.candidate_tz = candidate_tz
                slot.candidate_city_id = candidate_city_id
                slot.purpose = slot_purpose

                await session.flush()

                lock = SlotReservationLock(
                    slot_id=slot.id,
                    candidate_id=candidate_uuid,
                    candidate_tg_id=candidate_tg_id,
                    recruiter_id=slot.recruiter_id,
                    reservation_date=reservation_date,
                    expires_at=now_utc + timedelta(minutes=5),
                )
                session.add(lock)
                city_name = slot.city.name_plain if slot.city else None
                if city_name is None and candidate_city_id is not None:
                    city = await session.get(City, candidate_city_id)
                    if city:
                        city_name = city.name_plain
        except IntegrityError:
            await session.rollback()
            if candidate_tg_id is None or slot_recruiter_id is None:
                return ReservationResult(status="slot_taken")
            async with async_session() as check_session:
                existing_active = await check_session.scalar(
                    select(Slot)
                    .options(selectinload(Slot.recruiter), selectinload(Slot.city))
                    .where(
                        Slot.candidate_tg_id == candidate_tg_id,
                        Slot.recruiter_id == slot_recruiter_id,
                        Slot.purpose == slot_purpose,
                        func.lower(Slot.status).in_(
                            [
                                SlotStatus.PENDING,
                                SlotStatus.BOOKED,
                                SlotStatus.CONFIRMED_BY_CANDIDATE,
                            ]
                        ),
                    )
                    .order_by(Slot.start_utc.asc())
                )
            if existing_active:
                existing_active.start_utc = _to_aware_utc(existing_active.start_utc)
                return ReservationResult(status="duplicate_candidate", slot=existing_active)
            return ReservationResult(status="slot_taken")

        slot.start_utc = _to_aware_utc(slot.start_utc)
    if candidate_tg_id is not None:
        try:
            # For interview slots, new candidates start at TEST1_COMPLETED
            # (they've already passed Test1 before booking)
            initial_status = CandidateStatus.TEST1_COMPLETED if purpose == "interview" else None
            await create_or_update_user(
                telegram_id=candidate_tg_id,
                fio=candidate_fio,
                city=city_name or "",
                username=candidate_username,
                initial_status=initial_status,
                candidate_id=candidate_uuid,
                source="bot",
            )
        except Exception:
            # Candidate directory sync should not break reservation flow
            pass
        # Update candidate status to SLOT_PENDING (picked a slot, awaiting recruiter approval)
        if purpose == "interview":
            try:
                from backend.domain.candidates.status_service import set_status_slot_pending
                await set_status_slot_pending(candidate_tg_id)
            except Exception:
                logger.exception("Failed to update candidate status to SLOT_PENDING for %s", candidate_tg_id)
    return ReservationResult(status="reserved", slot=slot)


async def approve_slot(slot_id: int) -> Optional[Slot]:
    async with async_session() as session:
        async with session.begin():
            slot = await session.get(Slot, slot_id, with_for_update=True)
            status_value = (slot.status or "").lower() if slot else None
            allowed_statuses = {
                SlotStatus.PENDING,
                SlotStatus.BOOKED,
                SlotStatus.CONFIRMED_BY_CANDIDATE,
            }
            if not slot or status_value not in allowed_statuses:
                return None
            if status_value == SlotStatus.BOOKED:
                slot.start_utc = _to_aware_utc(slot.start_utc)
                return slot
            if status_value == SlotStatus.CONFIRMED_BY_CANDIDATE:
                slot.start_utc = _to_aware_utc(slot.start_utc)
                return slot

            slot.status = SlotStatus.BOOKED

            if slot.candidate_tg_id is not None:
                # Update candidate status to INTERVIEW_SCHEDULED
                try:
                    from backend.domain.candidates.status_service import set_status_interview_scheduled
                    await set_status_interview_scheduled(slot.candidate_tg_id)
                except Exception:
                    logger.exception("Failed to update candidate status to INTERVIEW_SCHEDULED for candidate %s", slot.candidate_tg_id)

                await add_outbox_notification(
                    notification_type="interview_confirmed_candidate",
                    booking_id=slot.id,
                    candidate_tg_id=slot.candidate_tg_id,
                    payload={
                        "event": "approved",
                        "slot_id": slot.id,
                    },
                    session=session,
                )

        if not slot:
            return None
        await session.refresh(slot)
        slot.start_utc = _to_aware_utc(slot.start_utc)
        return slot


async def reject_slot(
    slot_id: int,
    *,
    outbox_type: Optional[str] = None,
    outbox_payload: Optional[Dict[str, Any]] = None,
) -> Optional[Slot]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id, with_for_update=True)
        if not slot:
            return None
        reservation_date = _to_aware_utc(slot.start_utc).date()
        candidate_tg_id = slot.candidate_tg_id
        candidate_id = slot.candidate_id
        recruiter_id = slot.recruiter_id
        await session.execute(
            delete(SlotReservationLock).where(SlotReservationLock.slot_id == slot.id)
        )
        await session.execute(
            delete(NotificationLog).where(NotificationLog.booking_id == slot.id)
        )
        # Legacy notification logs (pre candidate binding) may still exist with NULL
        # ``candidate_tg_id``; remove them as well to avoid blocking future reuse.
        await session.execute(
            delete(NotificationLog)
            .where(NotificationLog.booking_id == slot.id)
            .where(NotificationLog.candidate_tg_id.is_(None))
        )
        if candidate_id is not None and recruiter_id is not None:
            await session.execute(
                delete(SlotReservationLock).where(
                    SlotReservationLock.candidate_id == candidate_id,
                    SlotReservationLock.recruiter_id == recruiter_id,
                    SlotReservationLock.reservation_date == reservation_date,
                )
            )
        elif candidate_tg_id is not None and recruiter_id is not None:
            await session.execute(
                delete(SlotReservationLock).where(
                    SlotReservationLock.candidate_tg_id == candidate_tg_id,
                    SlotReservationLock.recruiter_id == recruiter_id,
                    SlotReservationLock.reservation_date == reservation_date,
                )
            )
        # Update candidate status based on slot purpose before clearing candidate_tg_id
        if candidate_tg_id is not None:
            slot_purpose = getattr(slot, "purpose", "interview")
            try:
                if slot_purpose == "intro_day":
                    from backend.domain.candidates.status_service import (
                        get_candidate_status,
                        set_status_intro_day_declined_invitation,
                        set_status_intro_day_declined_day_of,
                    )
                    from backend.domain.candidates.status import CandidateStatus

                    # Check current status to determine which decline this is
                    current_status = await get_candidate_status(candidate_tg_id)

                    if current_status == CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY:
                        # This is a day-of decline (responding to 3H reminder)
                        await set_status_intro_day_declined_day_of(candidate_tg_id)
                    else:
                        # This is declining the initial invitation
                        await set_status_intro_day_declined_invitation(candidate_tg_id)
                else:
                    from backend.domain.candidates.status_service import set_status_interview_declined
                    await set_status_interview_declined(candidate_tg_id)
            except Exception:
                logger.exception("Failed to update candidate status to DECLINED for candidate %s (purpose=%s)", candidate_tg_id, slot_purpose)

        slot.status = SlotStatus.FREE
        slot.candidate_id = None
        slot.candidate_tg_id = None
        slot.candidate_fio = None
        slot.candidate_tz = None
        slot.candidate_city_id = None
        slot.purpose = "interview"
        if outbox_type and candidate_tg_id is not None:
            await add_outbox_notification(
                notification_type=outbox_type,
                booking_id=slot.id,
                candidate_tg_id=candidate_tg_id,
                recruiter_tg_id=None,
                payload=outbox_payload or {"event": outbox_type},
                session=session,
            )
        await session.commit()
        await session.refresh(slot)
        slot.start_utc = _to_aware_utc(slot.start_utc)
        return slot


async def set_recruiter_chat_id_by_command(name_hint: str, chat_id: int) -> Optional[Recruiter]:
    async with async_session() as session:
        rec = await session.scalar(select(Recruiter).where(Recruiter.name.ilike(name_hint)))
        if not rec:
            return None
        rec.tg_chat_id = chat_id
        await session.commit()
        return rec
