from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import datetime
from datetime import time as time_type
from datetime import timedelta, timezone
from typing import Dict, List, Optional, Tuple, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.services.bot_service import BotSendResult, BotService
from backend.apps.admin_ui.services.bot_service import (
    get_bot_service as resolve_bot_service,
)
from backend.apps.bot.services import (
    BookingNotificationStatus,
    SlotSnapshot,
    cancel_slot_reminders,
    capture_slot_snapshot,
    get_notification_service,
    get_state_manager as _get_state_manager,
    NotificationNotConfigured,
    approve_slot_and_notify,
    SlotApprovalResult,
)

try:  # pragma: no cover - optional dependency during tests
    from backend.apps.bot.reminders import get_reminder_service
except Exception:  # pragma: no cover - safe fallback when bot package unavailable
    get_reminder_service = None  # type: ignore[assignment]
from backend.apps.admin_ui.utils import (
    DEFAULT_TZ,
    fmt_local,
    norm_status,
    paginate,
    recruiter_time_to_utc,
    status_to_db,
)
from backend.core.audit import log_audit_action
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.apps.admin_ui.security import principal_ctx, Principal
from backend.domain import analytics
from backend.domain.models import (
    City,
    Recruiter,
    Slot,
    SlotStatus,
    ManualSlotAuditLog,
    DEFAULT_INTERVIEW_DURATION_MIN,
    SLOT_MIN_DURATION_MIN,
)
from backend.domain.candidates.models import User
from backend.domain.repositories import (
    approve_slot,
    reject_slot,
    reserve_slot,
    slot_status_free_clause,
)
from backend.domain.slot_service import ensure_slot_not_in_past, SlotValidationError
from backend.domain.errors import SlotOverlapError
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidate_status_service import CandidateStatusService
from backend.core.time_utils import ensure_aware_utc


def _resolve_hook(name: str, fallback):
    """Resolve callable from the core slots module so test monkeypatches are honored."""
    try:
        core_mod = importlib.import_module("backend.apps.admin_ui.services.slots")
        return getattr(core_mod, name, fallback)
    except Exception:
        return fallback


__all__ = [
    "list_slots",
    "recruiters_for_slot_form",
    "create_slot",
    "bulk_create_slots",
    "api_slots_payload",
    "delete_slot",
    "delete_all_slots",
    "schedule_manual_candidate_slot",
    "schedule_manual_candidate_slot_silent",
    "set_slot_outcome",
    "get_state_manager",
    "delete_past_free_slots",
    "execute_bot_dispatch",
    "reschedule_slot_booking",
    "reject_slot_booking",
    "ManualSlotError",
    "generate_default_day_slots",
]

_candidate_status_service = CandidateStatusService()


logger = logging.getLogger(__name__)


DEFAULT_COMPANY_NAME = "SMART SERVICE"
DEFAULT_SLOT_TZ = DEFAULT_TZ
REJECTION_TEMPLATE_KEY = "result_fail"


NotificationAction = Literal["reschedule", "reject"]


class ManualSlotError(Exception):
    """Raised when manual slot scheduling cannot be completed."""


def _ensure_recruiter_city_link(recruiter: Recruiter, city: City) -> bool:
    if city in recruiter.cities:
        return False
    recruiter.cities.append(city)
    return True


def _notification_feedback(action: NotificationAction, result) -> Tuple[str, bool]:
    status = getattr(result, "status", "") or ""
    reason = (getattr(result, "reason", "") or "").lower()
    notified = status in {"queued", "sent"}

    if action == "reschedule":
        queued_msg = "Слот освобождён. Уведомление поставлено в очередь."
        sent_msg = "Слот освобождён. Кандидату отправлено уведомление о переносе."
        failed_default = "Слот освобождён. Уведомление не отправлено."
        failed_broker = (
            "Слот освобождён. Сообщите кандидату вручную: брокер уведомлений недоступен."
        )
    else:
        queued_msg = "Слот освобождён. Уведомление об отмене поставлено в очередь."
        sent_msg = "Слот освобождён. Кандидату отправлено уведомление об отмене."
        failed_default = "Слот освобождён. Уведомление об отмене не отправлено."
        failed_broker = (
            "Слот освобождён. Уведомление об отмене не доставлено: брокер уведомлений недоступен."
        )

    if status == "queued":
        return queued_msg, True
    if status == "sent":
        if reason == "direct:no-broker":
            return "Слот освобождён. Отправлено напрямую (no-broker).", True
        return sent_msg, True
    if status == "failed":
        if reason == "broker_unavailable":
            return failed_broker, False
        return failed_default, False
    return failed_default, False


def get_state_manager():
    """Compatibility wrapper exposing the bot state manager."""

    return _get_state_manager()


async def generate_default_day_slots(
    *,
    recruiter_id: int,
    day: date_type,
    city_id: Optional[int] = None,
    duration_min: int = DEFAULT_INTERVIEW_DURATION_MIN,
) -> int:
    """Generate a standard working day of slots: 09:00-12:00 and 13:00-18:00, step 10m by default, lunch 12-13."""
    async with async_session() as session:
        recruiter = await session.get(
            Recruiter,
            recruiter_id,
            options=[selectinload(Recruiter.cities)],
        )
        if not recruiter:
            raise ValueError("Recruiter not found")
        # Resolve city: explicit choice or first available for recruiter; falls back to None.
        target_city = None
        if city_id:
            target_city = await session.get(City, city_id)
        if target_city is None:
            # Prefer the first linked city (ordered by name) if recruiter has any.
            target_city = next(
                iter(sorted(recruiter.cities, key=lambda c: (getattr(c, "name_plain", "") or "").lower())),
                None,
            )

        # Время генерации слотов в timezone рекрутера (единообразие с create_slot)
        recruiter_tz = getattr(recruiter, "tz", None) or DEFAULT_TZ
        candidate_tz = getattr(target_city, "tz", None) or recruiter_tz
        duration_min = max(duration_min, SLOT_MIN_DURATION_MIN)
        tz = ZoneInfo(recruiter_tz)
        tz_name = candidate_tz  # Для сохранения в слоты
        resolved_city_id = getattr(target_city, "id", None)

        def _period(start_h: int, end_h: int) -> List[datetime]:
            times: List[datetime] = []
            current = datetime.combine(day, time_type(hour=start_h, minute=0), tzinfo=tz)
            end_dt = datetime.combine(day, time_type(hour=end_h, minute=0), tzinfo=tz)
            while current < end_dt:
                times.append(current)
                current += timedelta(minutes=duration_min)
            return times

        local_times = _period(9, 12) + _period(13, 18)
        start_utc_list = [ensure_aware_utc(dt.astimezone(timezone.utc)) for dt in local_times]

        # Filter existing slots by exact UTC window of the requested local day to avoid TZ drift.
        day_start_local = datetime.combine(day, time_type.min, tzinfo=tz)
        day_end_local = datetime.combine(day, time_type.max, tzinfo=tz)
        day_start_utc = ensure_aware_utc(day_start_local.astimezone(timezone.utc))
        day_end_utc = ensure_aware_utc(day_end_local.astimezone(timezone.utc))

        # Ensure no conflicts across recruiters: each recruiter keeps own schedule,
        # but we still avoid duplicates for the same recruiter/time.
        existing_rows = await session.scalars(
            select(Slot.start_utc, Slot.recruiter_id, Slot.city_id).where(
                Slot.start_utc >= day_start_utc,
                Slot.start_utc <= day_end_utc,
                Slot.recruiter_id == recruiter_id,
            )
        )
        existing = {ensure_aware_utc(row[0]) for row in existing_rows if row and row[0] is not None}

        created = 0

        for start_utc in start_utc_list:
            try:
                ensure_slot_not_in_past(
                    start_utc,
                    slot_tz=recruiter_tz,
                )
            except SlotValidationError:
                # Stop generation once we hit a past slot to match previous behaviour.
                return created
            if start_utc in existing:
                continue
            slot = Slot(
                recruiter_id=recruiter_id,
                city_id=resolved_city_id,
                candidate_city_id=resolved_city_id,
                purpose="interview",
                tz_name=tz_name,
                start_utc=start_utc,
                duration_min=duration_min,
                status=SlotStatus.FREE,
            )
            session.add(slot)
            created += 1
        await session.commit()
        logger.info(
            "slots.generate_default",
            extra={
                "recruiter_id": recruiter_id,
                "city_id": resolved_city_id,
                "tz": tz_name,
                "day": day.isoformat(),
                "created_slots": created,
            },
        )
        return created


async def list_slots(
    recruiter_id: Optional[int],
    status: Optional[str],
    page: int,
    per_page: int,
    search_query: Optional[str] = None,
    city_name: Optional[str] = None,
    city_id: Optional[int] = None,
    day: Optional[date_type] = None,
    day_end: Optional[date_type] = None,
    principal: Optional[Principal] = None,
) -> Dict[str, object]:
    principal = principal or principal_ctx.get()
    if principal is None:
        from backend.core.settings import get_settings
        settings = get_settings()
        if settings.environment != "production":
            principal = Principal(type="admin", id=-1)
        else:
            raise RuntimeError("principal is required for list_slots")
    async with async_session() as session:
        filtered = select(Slot).where(func.coalesce(Slot.purpose, "interview") == "interview")
        if principal and principal.type == "recruiter":
            recruiter_id = principal.id
        if recruiter_id is not None:
            filtered = filtered.where(Slot.recruiter_id == recruiter_id)
        if status:
            filtered = filtered.where(Slot.status == status_to_db(status))
        if city_id is not None:
            filtered = filtered.where(Slot.city_id == city_id)
        elif city_name:
            # Backward-compatibility: allow filtering by city name for callers/tests
            filtered = filtered.where(Slot.city.has(City.name == city_name))
        if day is not None or day_end is not None:
            # Interpret day in default company timezone to align with generator UI.
            day_tz = ZoneInfo(DEFAULT_TZ)
            start_day = day or day_end
            end_day = day_end or day
            day_start_local = datetime.combine(start_day, time_type.min, tzinfo=day_tz)
            day_end_local = datetime.combine(end_day, time_type.max, tzinfo=day_tz)
            start_utc = ensure_aware_utc(day_start_local.astimezone(timezone.utc))
            end_utc = ensure_aware_utc(day_end_local.astimezone(timezone.utc))
            filtered = filtered.where(Slot.start_utc >= start_utc, Slot.start_utc <= end_utc)

        # Add search functionality
        if search_query:
            search_term = f"%{search_query.strip().lower()}%"
            # Join with recruiter and city tables for search
            filtered = filtered.outerjoin(Slot.recruiter).outerjoin(Slot.city)
            # Search in multiple fields
            from sqlalchemy import or_, cast, String
            filtered = filtered.where(
                or_(
                    func.lower(Slot.candidate_fio).like(search_term),
                    func.lower(cast(Slot.candidate_id, String)).like(search_term),
                    func.lower(cast(Slot.candidate_tg_id, String)).like(search_term),
                    func.lower(Recruiter.name).like(search_term),
                    func.lower(City.name).like(search_term),
                    func.lower(cast(Slot.status, String)).like(search_term),
                )
            )

        subquery = filtered.subquery()
        total = await session.scalar(select(func.count()).select_from(subquery)) or 0

        status_rows = (
            await session.execute(
                select(subquery.c.status, func.count())
                .select_from(subquery)
                .group_by(subquery.c.status)
            )
        ).all()

        aggregated: Dict[str, int] = {}
        for raw_status, count in status_rows:
            aggregated[norm_status(raw_status)] = int(count or 0)
        aggregated.setdefault("CONFIRMED_BY_CANDIDATE", 0)

        pages_total, page, offset = paginate(total, page, per_page)

        query = (
            filtered.options(
                selectinload(Slot.recruiter),
                selectinload(Slot.city),
            )
            .order_by(Slot.start_utc.desc())
            .offset(offset)
            .limit(per_page)
        )
        items = (await session.scalars(query)).all()

        candidate_ids = {slot.candidate_id for slot in items if slot.candidate_id}
        candidate_tg_ids = {slot.candidate_tg_id for slot in items if slot.candidate_tg_id}
        usernames: Dict[str, Optional[str]] = {}
        usernames_by_tg: Dict[int, Optional[str]] = {}
        user_ids_by_candidate: Dict[str, Optional[int]] = {}
        user_ids_by_tg: Dict[int, Optional[int]] = {}
        if candidate_ids:
            username_rows = await session.execute(
                select(User.candidate_id, User.id, User.username, User.telegram_username).where(
                    User.candidate_id.in_(candidate_ids)
                )
            )
            for candidate_id, user_id, username, telegram_username in username_rows:
                if candidate_id:
                    usernames[str(candidate_id)] = username or telegram_username
                    user_ids_by_candidate[str(candidate_id)] = user_id
        if candidate_tg_ids:
            username_rows = await session.execute(
                select(User.telegram_id, User.id, User.username, User.telegram_username).where(
                    User.telegram_id.in_(candidate_tg_ids)
                )
            )
            for tg_id, user_id, username, telegram_username in username_rows:
                if tg_id:
                    usernames_by_tg[int(tg_id)] = username or telegram_username
                    user_ids_by_tg[int(tg_id)] = user_id

        # Ensure all datetime fields are timezone-aware
        for item in items:
            if item.start_utc:
                item.start_utc = item.start_utc.replace(tzinfo=timezone.utc) if item.start_utc.tzinfo is None else item.start_utc
            if item.candidate_id:
                cid_key = str(item.candidate_id)
                item.candidate_username = usernames.get(cid_key)
                item.candidate_user_id = user_ids_by_candidate.get(cid_key)
            elif item.candidate_tg_id:
                tg_key = int(item.candidate_tg_id)
                item.candidate_username = usernames_by_tg.get(tg_key)
                item.candidate_user_id = user_ids_by_tg.get(tg_key)
            # Expunge to prevent lazy loading after session closes
            session.expunge(item)

    return {
        "items": items,
        "total": total,
        "page": page,
        "pages_total": pages_total,
        "status_counts": aggregated,
    }


async def recruiters_for_slot_form() -> List[Dict[str, object]]:
    inspector = sa_inspect(Recruiter)
    has_active = "active" in getattr(inspector, "columns", {})
    query = select(Recruiter).options(selectinload(Recruiter.cities)).order_by(Recruiter.name.asc())
    async with async_session() as session:
        recs = (await session.scalars(query)).all()
        if not recs:
            return []
    if has_active:
        active_recs = [rec for rec in recs if getattr(rec, "active", True)]
        if active_recs:
            recs = active_recs
    return [
        {
            "rec": rec,
            "cities": sorted(
                rec.cities,
                key=lambda city: (getattr(city, "name_plain", "") or "").lower(),
            ),
        }
        for rec in recs
    ]


async def create_slot(
    recruiter_id: int,
    date: str,
    time: str,
    *,
    city_id: int,
) -> bool:
    async with async_session() as session:
        recruiter = await session.get(
            Recruiter,
            recruiter_id,
            options=[selectinload(Recruiter.cities)],
        )
        if not recruiter:
            return False
        city = await session.get(City, city_id)
        if not city:
            return False
        linked = _ensure_recruiter_city_link(recruiter, city)
        recruiter_tz = getattr(recruiter, "tz", None) or DEFAULT_SLOT_TZ
        candidate_tz = getattr(city, "tz", None) or recruiter_tz

        # Время вводится в часовом поясе рекрутера, конвертируется в UTC.
        dt_utc = recruiter_time_to_utc(date, time, recruiter_tz)
        if not dt_utc:
            return False

        # Проверка, что слот не в прошлом (в UTC).
        try:
            ensure_slot_not_in_past(dt_utc, slot_tz=recruiter_tz)
        except SlotValidationError:
            return False

        # Проверяем пересечения вручную (особенно важно для SQLite без EXCLUDE CONSTRAINT).
        norm_start = _normalize_utc(dt_utc)
        new_end = norm_start + timedelta(minutes=DEFAULT_INTERVIEW_DURATION_MIN)
        existing_rows = await session.execute(
            select(Slot.start_utc, Slot.duration_min).where(Slot.recruiter_id == recruiter_id)
        )
        for existing_start, existing_duration in existing_rows:
            existing_norm = _normalize_utc(existing_start)
            duration = max(existing_duration or SLOT_MIN_DURATION_MIN, SLOT_MIN_DURATION_MIN)
            existing_end = existing_norm + timedelta(minutes=duration)
            if norm_start < existing_end and new_end > existing_norm:
                raise SlotOverlapError(recruiter_id=recruiter_id, start_utc=dt_utc)

        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value
        slot = Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            candidate_city_id=city_id,
            tz_name=candidate_tz,
            candidate_tz=candidate_tz,
            start_utc=dt_utc,
            duration_min=DEFAULT_INTERVIEW_DURATION_MIN,
            status=status_free,
        )
        session.add(slot)

        # Commit with proper error handling for exclusion constraint violations
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            # Check if this is a slot overlap exclusion constraint violation
            error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
            if 'slots_no_recruiter_time_overlap_excl' in error_msg or 'overlaps' in error_msg.lower():
                raise SlotOverlapError(
                    recruiter_id=recruiter_id,
                    start_utc=dt_utc,
                )
            # Re-raise other integrity errors (e.g., foreign key violations)
            raise

        await log_audit_action(
            "slot_created",
            "slot",
            getattr(slot, "id", None),
            changes={
                "recruiter_id": recruiter_id,
                "city_id": city_id,
                "city_linked": linked,
                "start_utc": dt_utc.isoformat(),
                "recruiter_tz": recruiter_tz,
                "candidate_tz": candidate_tz,
            },
        )
        return True


async def delete_slot(
    slot_id: int, *, force: bool = False, principal: Optional[Principal] = None
) -> Tuple[bool, Optional[str]]:
    principal = principal or principal_ctx.get()
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if not slot:
            return False, "Слот не найден"
        if principal and principal.type == "recruiter" and slot.recruiter_id != principal.id:
            return False, "Слот не найден"

        status = norm_status(slot.status)
        if not force and status not in {"FREE", "PENDING"}:
            return False, f"Нельзя удалить слот со статусом {status or 'UNKNOWN'}"

        had_candidate = bool(getattr(slot, "candidate_id", None) or getattr(slot, "candidate_tg_id", None))
        await session.delete(slot)
        await session.commit()
        await log_audit_action(
            "slot_deleted",
            "slot",
            slot_id,
            changes={
                "status": status,
                "had_candidate": had_candidate,
            },
        )

    if callable(get_reminder_service):
        try:
            await get_reminder_service().cancel_for_slot(slot_id)
        except RuntimeError:
            pass

    return True, None


async def delete_all_slots(*, force: bool = False, principal: Optional[Principal] = None) -> Tuple[int, int]:
    principal = principal or principal_ctx.get()
    async with async_session() as session:
        base_query = select(Slot.id)
        if principal and principal.type == "recruiter":
            base_query = base_query.where(Slot.recruiter_id == principal.id)
        total_before = await session.scalar(select(func.count()).select_from(base_query.subquery())) or 0
        if total_before == 0:
            return 0, 0

        slot_ids: List[int] = []

        if force:
            result = await session.execute(base_query)
            slot_ids = [row[0] for row in result]
            await session.execute(delete(Slot).where(Slot.id.in_(slot_ids)))
            await session.commit()
            remaining_after = 0
        else:
            allowed_statuses = {
                status_to_db("FREE"),
                status_to_db("PENDING"),
            }
            result = await session.execute(
                base_query.where(Slot.status.in_(allowed_statuses))
            )
            slot_ids = [row[0] for row in result]
            if not slot_ids:
                return 0, total_before
            await session.execute(delete(Slot).where(Slot.id.in_(slot_ids)))
            await session.commit()
            remaining_after = (
                await session.scalar(select(func.count()).select_from(base_query.subquery())) or 0
            )

    if callable(get_reminder_service):
        for sid in slot_ids:
            try:
                await get_reminder_service().cancel_for_slot(sid)
            except RuntimeError:
                break

    deleted = total_before - remaining_after
    await log_audit_action(
        "slots_bulk_deleted",
        "slot",
        None,
        changes={"deleted": deleted, "remaining": remaining_after, "forced": force},
    )
    return deleted, remaining_after


from sqlalchemy.ext.asyncio import AsyncSession

async def delete_past_free_slots(
    grace_minutes: int = 1,
    session: Optional[AsyncSession] = None,
    now_utc: Optional[datetime] = None,
) -> Tuple[int, int]:
    """
    Delete free interview slots that are already in the past.

    Deletes slots where:
    - start_time < (now - grace_minutes)
    - status is FREE
    - no candidate is assigned (candidate_id IS NULL AND candidate_tg_id IS NULL)

    Args:
        grace_minutes: optional grace period (default 1)
        session: optional DB session (for testing)
        now_utc: optional reference time (for testing)
    Returns:
        (deleted_count, total_checked)
    """
    now = now_utc or datetime.now(timezone.utc)
    threshold = now - timedelta(minutes=max(grace_minutes, 0))

    # Helper to run logic with a given session
    async def _process(sess: AsyncSession) -> Tuple[int, int]:
        # Strict query: only genuinely free slots
        candidates = await sess.execute(
            select(Slot.id, Slot.start_utc).where(
                slot_status_free_clause(Slot),
                Slot.candidate_id.is_(None),
                Slot.candidate_tg_id.is_(None),
                Slot.start_utc < threshold,
            )
        )
        stale_ids: List[int] = []
        for slot_id, start_utc in candidates:
            # Verify in Python to ensure timezone-aware comparison matches
            if ensure_aware_utc(start_utc) < threshold:
                stale_ids.append(slot_id)

        count = len(stale_ids)
        if count == 0:
            return 0, 0

        await sess.execute(delete(Slot).where(Slot.id.in_(stale_ids)))
        await sess.commit()
        return count, count

    if session:
        return await _process(session)
    
    async with async_session() as sess:
        return await _process(sess)


def _reservation_error_message(status: str) -> str:
    messages = {
        "slot_taken": "На выбранное время уже есть слот. Попробуйте другое время.",
        "duplicate_candidate": "У кандидата уже назначено собеседование.",
        "already_reserved": "У кандидата уже забронирован слот на эту дату.",
    }
    return messages.get(status, "Не удалось забронировать слот. Попробуйте другое время.")


async def _log_manual_slot_assignment(
    *,
    slot_id: int,
    candidate_tg_id: Optional[int],
    recruiter_id: int,
    city_id: int,
    slot_datetime_utc: datetime,
    slot_tz: str,
    admin_username: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    custom_message_sent: bool,
    custom_message_text: Optional[str],
    candidate_previous_status: Optional[str],
) -> None:
    """Log manual slot assignment to audit table."""
    if candidate_tg_id is None:
        return
    try:
        async with async_session() as session:
            audit_log = ManualSlotAuditLog(
                slot_id=slot_id,
                candidate_tg_id=candidate_tg_id,
                recruiter_id=recruiter_id,
                city_id=city_id,
                slot_datetime_utc=slot_datetime_utc,
                slot_tz=slot_tz,
                purpose="interview",
                custom_message_sent=custom_message_sent,
                custom_message_text=custom_message_text,
                admin_username=admin_username,
                ip_address=ip_address,
                user_agent=user_agent,
                candidate_previous_status=candidate_previous_status,
            )
            session.add(audit_log)
            await session.commit()
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.error("Failed to log manual slot assignment to audit: %s", exc, exc_info=True)


async def schedule_manual_candidate_slot(
    *,
    candidate: "User",
    recruiter: Recruiter,
    city: City,
    dt_utc: datetime,
    slot_tz: str,
    duration_min: int = DEFAULT_INTERVIEW_DURATION_MIN,
    admin_username: str = "admin",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    custom_message_sent: bool = False,
    custom_message_text: Optional[str] = None,
    principal: Optional[Principal] = None,
) -> SlotApprovalResult:
    if candidate.telegram_id is None:
        raise ManualSlotError("Для кандидата не указан Telegram ID.")

    principal = principal or principal_ctx.get()
    if principal and principal.type == "recruiter" and recruiter.id != principal.id:
        raise ManualSlotError("Слот не найден или недоступен.")

    normalized_dt = ensure_aware_utc(dt_utc)
    requested_duration = max(SLOT_MIN_DURATION_MIN, duration_min)
    new_slot_end = normalized_dt + timedelta(minutes=requested_duration)

    async with async_session() as session:
        # Check for exact duplicate
        existing = await session.scalar(
            select(Slot.id)
            .where(Slot.recruiter_id == recruiter.id)
            .where(Slot.start_utc == normalized_dt)
        )
        if existing:
            raise ManualSlotError("На выбранное время уже существует слот у этого рекрутёра.")

        # Check for overlapping slots strictly by real durations (no extra padding)
        # Fetch nearby slots in a reasonable window around the requested time.
        surrounding_start = normalized_dt - timedelta(hours=2)
        surrounding_end = new_slot_end + timedelta(hours=2)
        overlapping_slots = await session.execute(
            select(Slot.id, Slot.start_utc, Slot.duration_min)
            .where(Slot.recruiter_id == recruiter.id)
            .where(Slot.start_utc >= surrounding_start)
            .where(Slot.start_utc <= surrounding_end)
        )
        conflict_times: List[str] = []
        for _conflict_id, conflict_start, conflict_duration in overlapping_slots:
            conflict_start_utc = ensure_aware_utc(conflict_start)
            conflict_end = conflict_start_utc + timedelta(minutes=conflict_duration or SLOT_MIN_DURATION_MIN)

            # Overlaps if: (new_start < conflict_end) AND (new_end > conflict_start)
            if normalized_dt < conflict_end and new_slot_end > conflict_start_utc:
                conflict_time_str = fmt_local(conflict_start_utc, slot_tz)
                conflict_times.append(conflict_time_str)

        if conflict_times:
            raise ManualSlotError(
                f"Конфликт расписания: у рекрутёра уже есть слот(ы) в это время: {', '.join(conflict_times)}."
            )

        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=slot_tz,
            start_utc=normalized_dt,
            status=status_free,
            duration_min=requested_duration,
        )
        session.add(slot)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            error_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
            if (
                "slots_no_recruiter_time_overlap_excl" in error_msg
                or "overlaps" in error_msg.lower()
            ):
                raise ManualSlotError(
                    "У рекрутёра уже есть слот в это время. Выберите другое окно."
                ) from exc
            raise
        await session.refresh(slot)
        slot_id = slot.id

    reserve_fn = _resolve_hook("reserve_slot", reserve_slot)
    reservation = await reserve_fn(
        slot_id,
        candidate.telegram_id,
        candidate.fio,
        slot_tz,
        candidate_id=candidate.candidate_id,
        candidate_city_id=city.id,
        candidate_username=candidate.username,
        purpose="interview",
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
        allow_candidate_replace=False,  # Manual scheduling should fail if candidate already has a slot
    )

    if reservation.status != "reserved":
        await delete_slot(slot_id, force=True)
        raise ManualSlotError(_reservation_error_message(reservation.status))

    approve_fn = _resolve_hook("approve_slot_and_notify", approve_slot_and_notify)
    result = await approve_fn(slot_id, force_notify=True)
    if result.status in {"approved", "notify_failed", "already"}:
        # Log manual slot assignment to audit table
        await _log_manual_slot_assignment(
            slot_id=slot_id,
            candidate_tg_id=candidate.telegram_id,
            recruiter_id=recruiter.id,
            city_id=city.id,
            slot_datetime_utc=normalized_dt,
            slot_tz=slot_tz,
            admin_username=admin_username,
            ip_address=ip_address,
            user_agent=user_agent,
            custom_message_sent=custom_message_sent,
            custom_message_text=custom_message_text,
            candidate_previous_status=candidate.candidate_status.value if candidate.candidate_status else None,
        )
        return result

    raise ManualSlotError(result.message or "Не удалось согласовать слот.")


async def schedule_manual_candidate_slot_silent(
    *,
    candidate: "User",
    recruiter: Recruiter,
    city: City,
    dt_utc: datetime,
    slot_tz: str,
    duration_min: int = DEFAULT_INTERVIEW_DURATION_MIN,
    admin_username: str = "admin",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    principal: Optional[Principal] = None,
) -> SlotApprovalResult:
    """Schedule a slot without candidate notification (manual lead flow)."""
    principal = principal or principal_ctx.get()
    if principal and principal.type == "recruiter" and recruiter.id != principal.id:
        raise ManualSlotError("Слот не найден или недоступен.")
    normalized_dt = ensure_aware_utc(dt_utc)
    requested_duration = max(SLOT_MIN_DURATION_MIN, duration_min)
    overlap_end = normalized_dt + timedelta(minutes=SLOT_MIN_DURATION_MIN)

    async with async_session() as session:
        existing = await session.scalar(
            select(Slot.id)
            .where(Slot.recruiter_id == recruiter.id)
            .where(Slot.start_utc == normalized_dt)
        )
        if existing:
            raise ManualSlotError("На выбранное время уже существует слот у этого рекрутёра.")

        surrounding_start = normalized_dt - timedelta(hours=2)
        surrounding_end = new_slot_end + timedelta(hours=2)
        overlapping_slots = await session.execute(
            select(Slot.id, Slot.start_utc, Slot.duration_min)
            .where(Slot.recruiter_id == recruiter.id)
            .where(Slot.start_utc >= surrounding_start)
            .where(Slot.start_utc <= surrounding_end)
        )
        conflict_times: List[str] = []
        for _conflict_id, conflict_start, conflict_duration in overlapping_slots:
            conflict_start_utc = ensure_aware_utc(conflict_start)
            conflict_end = conflict_start_utc + timedelta(minutes=SLOT_MIN_DURATION_MIN)
            if normalized_dt < conflict_end and overlap_end > conflict_start_utc:
                conflict_time_str = fmt_local(conflict_start_utc, slot_tz)
                conflict_times.append(conflict_time_str)

        if conflict_times:
            raise ManualSlotError(
                "Конфликт расписания: у рекрутёра уже есть слот(ы) в это время: "
                f"{', '.join(conflict_times)}."
            )

        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=slot_tz,
            start_utc=normalized_dt,
            status=status_free,
            duration_min=requested_duration,
        )
        session.add(slot)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            error_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
            if (
                "slots_no_recruiter_time_overlap_excl" in error_msg
                or "overlaps" in error_msg.lower()
            ):
                raise ManualSlotError(
                    "У рекрутёра уже есть слот в это время. Выберите другое окно."
                ) from exc
            raise
        await session.refresh(slot)
        slot_id = slot.id

    reservation = await reserve_slot(
        slot_id,
        candidate.telegram_id,
        candidate.fio,
        slot_tz,
        candidate_id=candidate.candidate_id,
        candidate_city_id=city.id,
        candidate_username=candidate.username,
        purpose="interview",
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
        allow_candidate_replace=False,
    )

    if reservation.status != "reserved":
        await delete_slot(slot_id, force=True)
        raise ManualSlotError(_reservation_error_message(reservation.status))

    slot = await approve_slot(slot_id)
    if not slot:
        await delete_slot(slot_id, force=True)
        raise ManualSlotError("Не удалось согласовать слот.")

    async with async_session() as session:
        user = await session.get(User, candidate.id)
        if user and user.candidate_status != CandidateStatus.INTERVIEW_SCHEDULED:
            await _candidate_status_service.force(
                user,
                CandidateStatus.INTERVIEW_SCHEDULED,
                reason="manual slot assignment",
            )
            await session.commit()
            try:
                await analytics.log_funnel_event(
                    analytics.FunnelEvent.SLOT_BOOKED,
                    user_id=user.telegram_id,
                    candidate_id=user.id,
                    metadata={"status": CandidateStatus.INTERVIEW_SCHEDULED.value, "source": "manual"},
                )
            except Exception:
                logger.exception(
                    "Failed to log SLOT_BOOKED for manual slot assignment",
                    extra={"candidate_id": user.id},
                )

    await _log_manual_slot_assignment(
        slot_id=slot_id,
        candidate_tg_id=candidate.telegram_id,
        recruiter_id=recruiter.id,
        city_id=city.id,
        slot_datetime_utc=normalized_dt,
        slot_tz=slot_tz,
        admin_username=admin_username,
        ip_address=ip_address,
        user_agent=user_agent,
        custom_message_sent=False,
        custom_message_text=None,
        candidate_previous_status=candidate.candidate_status.value if candidate.candidate_status else None,
    )

    return SlotApprovalResult(
        status="approved",
        message="Слот согласован без уведомления кандидата.",
        slot=slot,
    )


@dataclass
class BotDispatchPlan:
    kind: str
    slot_id: int
    candidate_id: int
    candidate_tz: Optional[str] = None
    candidate_city_id: Optional[int] = None
    candidate_name: str = ""
    recruiter_name: Optional[str] = None
    template_key: Optional[str] = None
    template_context: Dict[str, object] = field(default_factory=dict)
    scheduled_at: Optional[datetime] = None
    required: Optional[bool] = None


@dataclass
class BotDispatch:
    status: str
    plan: Optional[BotDispatchPlan] = None


async def set_slot_outcome(
    slot_id: int,
    outcome: str,
    *,
    bot_service: Optional[BotService] = None,
    principal: Optional[Principal] = None,
) -> Tuple[bool, Optional[str], Optional[str], Optional[BotDispatch]]:
    normalized = (outcome or "").strip().lower()
    aliases = {"passed": "success", "failed": "reject"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"success", "reject"}:
        return (
            False,
            "Некорректный исход. Выберите «Прошёл» или «Не прошёл».",
            None,
            None,
        )

    service = bot_service
    if service is None:
        try:
            service = resolve_bot_service()
        except RuntimeError:
            service = None

    principal = principal or principal_ctx.get()
    async with async_session() as session:
        slot = await session.scalar(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(Slot.id == slot_id)
        )
        if not slot:
            return False, "Слот не найден.", None, None
        if principal and principal.type == "recruiter" and slot.recruiter_id != principal.id:
            return False, "Слот не найден.", None, None
        if not getattr(slot, "candidate_tg_id", None):
            return (
                False,
                "Слот не привязан к кандидату, отправить сообщение нельзя.",
                None,
                None,
            )

        slot.interview_outcome = normalized

        dispatch: Optional[BotDispatch]
        if normalized == "success":
            dispatch = _plan_test2_dispatch(slot, service)
        else:
            dispatch = _plan_rejection_dispatch(slot, service)

        await session.commit()
        await log_audit_action(
            "slot_outcome_set",
            "slot",
            slot_id,
            changes={
                "outcome": normalized,
                "candidate_present": bool(getattr(slot, "candidate_tg_id", None)),
            },
        )

    message = _format_outcome_message(normalized, dispatch.status if dispatch else None)
    reminder_service = None
    if callable(get_reminder_service):
        try:
            reminder_service = get_reminder_service()
        except RuntimeError:
            reminder_service = None
    if reminder_service is not None:
        await reminder_service.cancel_for_slot(slot_id)
    return True, message, normalized, dispatch


def _plan_test2_dispatch(slot: Slot, service: Optional[BotService]) -> BotDispatch:
    if slot.test2_sent_at is not None:
        return BotDispatch(status="skipped:already_sent")

    if service is None:
        return BotDispatch(status="skipped:not_configured")

    if not service.enabled:
        return BotDispatch(status="skipped:disabled")

    if not service.is_ready():
        return BotDispatch(status="skipped:not_configured")

    scheduled_at = datetime.now(timezone.utc)
    slot.test2_sent_at = scheduled_at

    candidate_id = int(slot.candidate_tg_id)
    plan = BotDispatchPlan(
        kind="test2",
        slot_id=slot.id,
        candidate_id=candidate_id,
        candidate_tz=getattr(slot, "candidate_tz", None),
        candidate_city_id=getattr(slot, "candidate_city_id", None),
        candidate_name=getattr(slot, "candidate_fio", "") or "",
        scheduled_at=scheduled_at,
        required=get_settings().test2_required,
    )
    return BotDispatch(status="sent_test2", plan=plan)


def _plan_rejection_dispatch(slot: Slot, service: Optional[BotService]) -> BotDispatch:
    if slot.rejection_sent_at is not None:
        return BotDispatch(status="skipped:already_sent")

    if service is None:
        return BotDispatch(status="skipped:not_configured")

    if not service.enabled:
        return BotDispatch(status="skipped:disabled")

    if not service.is_ready():
        return BotDispatch(status="skipped:not_configured")

    scheduled_at = datetime.now(timezone.utc)
    slot.rejection_sent_at = scheduled_at

    candidate_id = int(slot.candidate_tg_id)
    plan = BotDispatchPlan(
        kind="rejection",
        slot_id=slot.id,
        candidate_id=candidate_id,
        candidate_name=getattr(slot, "candidate_fio", "") or "",
        candidate_city_id=getattr(slot, "candidate_city_id", None),
        recruiter_name=slot.recruiter.name if slot.recruiter else None,
        template_key=REJECTION_TEMPLATE_KEY,
        template_context={
            "candidate_fio": getattr(slot, "candidate_fio", "") or "",
            "company_name": DEFAULT_COMPANY_NAME,
            "city_name": slot.city.name_plain if slot.city else "",
            "recruiter_name": slot.recruiter.name if slot.recruiter else "",
        },
        scheduled_at=scheduled_at,
    )
    return BotDispatch(status="sent_rejection", plan=plan)


def _format_outcome_message(outcome: str, status: Optional[str]) -> str:
    if outcome == "success":
        base = "Исход «Прошёл» сохранён."
        if status == "sent_test2":
            return base + " Кандидату отправлен Тест 2."
        if status == "skipped:already_sent":
            return base + " Тест 2 уже отправлялся ранее."
        if status == "skipped:disabled":
            return base + " Отправка Теста 2 отключена."
        if status == "skipped:not_configured":
            return base + " Бот не настроен."
        return base

    base = "Исход «Не прошёл» сохранён."
    if status == "sent_rejection":
        return base + " Кандидату отправлен отказ."
    if status == "skipped:already_sent":
        return base + " Отказ уже был отправлен ранее."
    if status == "skipped:disabled":
        return base + " Отправка сообщений отключена."
    if status == "skipped:not_configured":
        return base + " Бот не настроен."
    return base


async def execute_bot_dispatch(
    plan: BotDispatchPlan, outcome: str, service: BotService
) -> None:
    bot_ready = service.is_ready()
    action_result = "skipped:error"
    success = False

    try:
        if plan.kind == "test2":
            result = await _trigger_test2(
                plan.candidate_id,
                plan.candidate_tz,
                plan.candidate_city_id,
                plan.candidate_name,
                bot_service=service,
                required=plan.required,
                slot_id=plan.slot_id,
            )
            action_result = _map_test2_status(result.status)
            success = result.ok and action_result == "sent_test2"
        elif plan.kind == "rejection":
            result = await _trigger_rejection(
                plan.candidate_id,
                plan.template_key or REJECTION_TEMPLATE_KEY,
                plan.template_context,
                city_id=plan.candidate_city_id,
                bot_service=service,
            )
            action_result = result.status
            success = result.ok and result.status == "sent_rejection"
        else:
            logger.warning("Unknown bot dispatch kind: %s", plan.kind)
            action_result = "skipped:unknown"
            success = False
    except Exception:  # pragma: no cover - defensive logging
        logger.exception("Failed to execute bot dispatch for slot %s", plan.slot_id)
        action_result = "skipped:error"
        success = False

    await _mark_dispatch_state(plan.slot_id, plan.kind, success)

    logger.info(
        "bot.dispatch.outcome",
        extra={
            "slot_id": plan.slot_id,
            "candidate_id": plan.candidate_id,
            "outcome": outcome,
            "bot_ready": bot_ready,
            "action_result": action_result,
        },
    )


def _map_test2_status(status: str) -> str:
    if status == "sent":
        return "sent_test2"
    return status


async def _mark_dispatch_state(slot_id: int, kind: str, success: bool) -> None:
    field = "test2_sent_at" if kind == "test2" else "rejection_sent_at"
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if not slot:
            return
        if success:
            setattr(slot, field, datetime.now(timezone.utc))
        else:
            setattr(slot, field, None)
        await session.commit()


async def _trigger_test2(
    candidate_id: int,
    candidate_tz: Optional[str],
    candidate_city: Optional[int],
    candidate_name: str,
    *,
    bot_service: Optional[BotService],
    required: bool,
    slot_id: Optional[int] = None,
) -> BotSendResult:
    service = bot_service
    if service is None:
        try:
            service = resolve_bot_service()
        except RuntimeError:
            logger.warning("Bot services are not configured; cannot send Test 2.")
            if required:
                return BotSendResult(
                    ok=False,
                    status="skipped:not_configured",
                    error="Бот недоступен. Проверьте его конфигурацию.",
                )
            return BotSendResult(
                ok=True,
                status="skipped:not_configured",
                message="Отправка Теста 2 пропущена: бот не настроен.",
            )

    return await service.send_test2(
        candidate_id,
        candidate_tz,
        candidate_city,
        candidate_name,
        required=required,
        slot_id=slot_id,
    )


async def reschedule_slot_booking(slot_id: int, principal: Optional[Principal] = None) -> Tuple[bool, str, bool]:
    principal = principal or principal_ctx.get()
    async with async_session() as session:
        slot = await session.scalar(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(Slot.id == slot_id)
        )

    if not slot:
        return False, "Слот не найден.", False
    if principal and principal.type == "recruiter" and slot.recruiter_id != principal.id:
        return False, "Слот не найден.", False
    has_candidate = slot.candidate_tg_id is not None or slot.candidate_id is not None
    if not has_candidate:
        return False, "Слот не привязан к кандидату.", False

    snapshot: Optional[SlotSnapshot] = await capture_slot_snapshot(slot) if slot.candidate_tg_id else None
    try:
        notification_service = get_notification_service()
    except NotificationNotConfigured:
        notification_service = None

    await reject_slot(slot_id)
    await cancel_slot_reminders(slot_id)

    if notification_service is None or slot.candidate_tg_id is None:
        message = (
            "Слот освобождён. Уведомления не отправлены (нет Telegram ID)."
            if slot.candidate_tg_id is None
            else "Слот освобождён. Уведомления не отправлены (сервис недоступен)."
        )
        await log_audit_action(
            "slot_reschedule_requested",
            "slot",
            slot_id,
            changes={"notified": False, "has_candidate": has_candidate},
        )
        return True, message, False

    try:
        result = await notification_service.on_booking_status_changed(
            slot_id,
            BookingNotificationStatus.RESCHEDULE_REQUESTED,
            snapshot=snapshot,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to send reschedule notification, freeing slot anyway: %s", exc, exc_info=True)
        await log_audit_action(
            "slot_reschedule_requested",
            "slot",
            slot_id,
            changes={"notified": False, "error": str(exc)},
        )
        return True, "Слот освобождён. Уведомления не отправлены (ошибка отправки).", False

    message, notified = _notification_feedback("reschedule", result)
    await log_audit_action(
        "slot_reschedule_requested",
        "slot",
        slot_id,
        changes={"notified": notified},
    )
    return True, message, notified


async def reject_slot_booking(slot_id: int, principal: Optional[Principal] = None) -> Tuple[bool, str, bool]:
    principal = principal or principal_ctx.get()
    async with async_session() as session:
        slot = await session.scalar(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(Slot.id == slot_id)
        )

    if not slot:
        return False, "Слот не найден.", False
    if principal and principal.type == "recruiter" and slot.recruiter_id != principal.id:
        return False, "Слот не найден.", False
    has_candidate = slot.candidate_tg_id is not None or slot.candidate_id is not None
    if not has_candidate:
        return False, "Слот не привязан к кандидату.", False

    snapshot: Optional[SlotSnapshot] = await capture_slot_snapshot(slot) if slot.candidate_tg_id else None
    try:
        notification_service = get_notification_service()
    except NotificationNotConfigured:
        notification_service = None

    await reject_slot(slot_id)
    await cancel_slot_reminders(slot_id)

    if notification_service is None or slot.candidate_tg_id is None:
        message = (
            "Слот освобождён. Уведомления не отправлены (нет Telegram ID)."
            if slot.candidate_tg_id is None
            else "Слот освобождён. Уведомления не отправлены (сервис недоступен)."
        )
        await log_audit_action(
            "slot_booking_rejected",
            "slot",
            slot_id,
            changes={"notified": False, "has_candidate": has_candidate},
        )
        return True, message, False

    try:
        result = await notification_service.on_booking_status_changed(
            slot_id,
            BookingNotificationStatus.CANCELLED,
            snapshot=snapshot,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to send rejection notification, freeing slot anyway: %s", exc, exc_info=True)
        await log_audit_action(
            "slot_booking_rejected",
            "slot",
            slot_id,
            changes={"notified": False, "error": str(exc)},
        )
        return True, "Слот освобождён. Уведомления не отправлены (ошибка отправки).", False

    message, notified = _notification_feedback("reject", result)
    await log_audit_action(
        "slot_booking_rejected",
        "slot",
        slot_id,
        changes={"notified": notified},
    )
    return True, message, notified



async def _trigger_rejection(
    candidate_id: int,
    template_key: str,
    context: Dict[str, object],
    *,
    city_id: Optional[int],
    bot_service: Optional[BotService],
) -> BotSendResult:
    service = bot_service
    if service is None:
        try:
            service = resolve_bot_service()
        except RuntimeError:
            logger.warning(
                "Bot services are not configured; cannot send rejection message."
            )
            return BotSendResult(
                ok=False,
                status="skipped:not_configured",
                error="Бот недоступен. Проверьте его конфигурацию.",
            )

    return await service.send_rejection(
        candidate_id,
        city_id=city_id,
        template_key=template_key,
        context=context,
    )


def _normalize_utc(dt: datetime) -> datetime:
    """Return UTC naive datetime for reliable comparisons across drivers."""
    if dt.tzinfo is None:
        # Assume already UTC naive
        return dt.replace(tzinfo=None)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _as_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware UTC for database comparisons."""
    return ensure_aware_utc(dt)


async def bulk_create_slots(
    recruiter_id: int,
    start_date: str,
    end_date: str,
    start_time: str,
    end_time: str,
    break_start: str,
    break_end: str,
    step_min: int,
    include_weekends: bool,
    use_break: bool,
    *,
    city_id: int,
) -> Tuple[int, Optional[str]]:
    async with async_session() as session:
        recruiter = await session.get(
            Recruiter,
            recruiter_id,
            options=[selectinload(Recruiter.cities)],
        )
        if not recruiter:
            return 0, "Рекрутёр не найден"

        city = await session.get(City, city_id)
        if not city:
            return 0, "Город не найден"
        linked = _ensure_recruiter_city_link(recruiter, city)

        try:
            start = date_type.fromisoformat(start_date)
            end = date_type.fromisoformat(end_date)
        except ValueError:
            return 0, "Некорректные даты"
        if end < start:
            return 0, "Дата окончания раньше даты начала"

        try:
            window_start = time_type.fromisoformat(start_time)
            window_end = time_type.fromisoformat(end_time)
            pause_start = time_type.fromisoformat(break_start)
            pause_end = time_type.fromisoformat(break_end)
        except ValueError:
            return 0, "Некорректное время"

        if window_end <= window_start:
            return 0, "Время окончания должно быть позже времени начала"
        if step_min < SLOT_MIN_DURATION_MIN:
            return 0, f"Шаг должен быть не меньше {SLOT_MIN_DURATION_MIN} минут"

        if use_break and pause_end <= pause_start:
            return 0, "Время окончания перерыва должно быть позже его начала"

        start_minutes = window_start.hour * 60 + window_start.minute
        end_minutes = window_end.hour * 60 + window_end.minute
        break_start_minutes = pause_start.hour * 60 + pause_start.minute
        break_end_minutes = pause_end.hour * 60 + pause_end.minute

        recruiter_tz = getattr(recruiter, "tz", None) or DEFAULT_SLOT_TZ
        city_tz = getattr(city, "tz", None) or recruiter_tz

        planned_pairs: List[Tuple[datetime, datetime]] = []  # (original, normalized)
        planned_norms = set()
        current_date = start
        while current_date <= end:
            if include_weekends or current_date.weekday() < 5:
                current_minutes = start_minutes
                while current_minutes < end_minutes:
                    if (
                        use_break
                        and break_start_minutes < break_end_minutes
                        and break_start_minutes <= current_minutes < break_end_minutes
                    ):
                        current_minutes += step_min
                        continue

                    hours, minutes = divmod(current_minutes, 60)
                    time_str = f"{hours:02d}:{minutes:02d}"
                    # Время задаётся в часовом поясе рекрутера, конвертируется в UTC.
                    dt_utc = recruiter_time_to_utc(
                        current_date.isoformat(), time_str, recruiter_tz
                    )
                    if not dt_utc:
                        return 0, "Не удалось преобразовать время в UTC"

                    # Пропускаем прошлые даты/время (валидация через domain service).
                    try:
                        ensure_slot_not_in_past(dt_utc, slot_tz=recruiter_tz)
                    except SlotValidationError:
                        current_minutes += step_min
                        continue

                    norm_dt = _normalize_utc(dt_utc)
                    if norm_dt not in planned_norms:
                        planned_norms.add(norm_dt)
                        planned_pairs.append((dt_utc, norm_dt))
                    current_minutes += step_min
            current_date += timedelta(days=1)

        if not planned_pairs:
            return 0, "Нет доступных слотов для создания"

        norm_values = [norm for _, norm in planned_pairs]
        range_start = min(norm_values)
        range_end = max(norm_values)

        existing_rows = await session.scalars(
            select(Slot.start_utc)
            .where(Slot.recruiter_id == recruiter_id)
            .where(Slot.start_utc >= _as_utc(range_start))
            .where(Slot.start_utc <= _as_utc(range_end))
        )
        existing_norms = {_normalize_utc(dt) for dt in existing_rows}

        to_insert = [
            original for original, norm in planned_pairs if norm not in existing_norms
        ]
        if not to_insert:
            return 0, None

        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value

        session.add_all(
            [
                Slot(
                    recruiter_id=recruiter_id,
                    city_id=city_id,
                    candidate_city_id=city_id,
                    start_utc=dt,
                    status=status_free,
                    duration_min=max(step_min, SLOT_MIN_DURATION_MIN),
                    tz_name=city_tz,
                    candidate_tz=city_tz,
                )
                for dt in to_insert
            ]
        )

        # Commit with proper error handling for exclusion constraint violations
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            # Check if this is a slot overlap exclusion constraint violation
            error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
            if 'slots_no_recruiter_time_overlap_excl' in error_msg or 'overlaps' in error_msg.lower():
                return 0, "У рекрутера уже есть слоты в выбранное время. Проверьте расписание и попробуйте другой интервал."
            # Re-raise other integrity errors
            raise

        await log_audit_action(
            "slots_bulk_created",
            "slot",
            None,
            changes={
                "created": len(to_insert),
                "recruiter_id": recruiter_id,
                "city_id": city_id,
                "city_linked": linked,
            },
        )
        return len(to_insert), None


def _format_slot_local_time(slot: Slot, tz_override: Optional[str] = None) -> str:
    tz_label = tz_override or getattr(slot, "tz_name", None) or DEFAULT_SLOT_TZ
    start = slot.start_utc
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    try:
        zone = ZoneInfo(tz_label)
    except Exception:
        zone = ZoneInfo(DEFAULT_SLOT_TZ)
    return start.astimezone(zone).isoformat()


async def api_slots_payload(
    recruiter_id: Optional[int],
    status: Optional[str],
    limit: int,
) -> List[Dict[str, object]]:
    async with async_session() as session:
        query = (
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .order_by(Slot.start_utc.asc())
            .where(func.coalesce(Slot.purpose, "interview") == "interview")
        )
        if recruiter_id is not None:
            query = query.where(Slot.recruiter_id == recruiter_id)
        if status:
            query = query.where(Slot.status == status_to_db(status))
        if limit:
            query = query.limit(max(1, min(500, limit)))
        slots = (await session.scalars(query)).all()
    payload: List[Dict[str, object]] = []
    for sl in slots:
        recruiter_tz = None
        if sl.recruiter and getattr(sl.recruiter, "tz", None):
            recruiter_tz = sl.recruiter.tz
        slot_tz = recruiter_tz or getattr(sl, "tz_name", None) or DEFAULT_SLOT_TZ
        candidate_tz = getattr(sl, "candidate_tz", None)
        payload.append(
            {
                "id": sl.id,
                "recruiter_id": sl.recruiter_id,
                "recruiter_name": sl.recruiter.name if sl.recruiter else None,
                "start_utc": sl.start_utc.isoformat(),
                "status": norm_status(sl.status),
                "candidate_fio": getattr(sl, "candidate_fio", None),
                "candidate_tg_id": getattr(sl, "candidate_tg_id", None),
                "candidate_tz": candidate_tz,
                "tz_name": getattr(sl, "tz_name", None),
                "recruiter_tz": recruiter_tz,
                "recruiter_local_time": _format_slot_local_time(sl, slot_tz),
                "candidate_local_time": _format_slot_local_time(sl, candidate_tz) if candidate_tz else None,
                "city_name": sl.city.name if sl.city else None,
            }
        )
    return payload
