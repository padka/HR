from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import datetime
from datetime import time as time_type
from datetime import timedelta, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.services.bot_service import BotSendResult, BotService
from backend.apps.admin_ui.services.bot_service import (
    get_bot_service as resolve_bot_service,
)
from backend.apps.bot.services import (
    BookingNotificationStatus,
    NotificationService,
    SlotSnapshot,
    cancel_slot_reminders,
    capture_slot_snapshot,
    get_notification_service,
    get_state_manager as _get_state_manager,
)

try:  # pragma: no cover - optional dependency during tests
    from backend.apps.bot.reminders import get_reminder_service
except Exception:  # pragma: no cover - safe fallback when bot package unavailable
    get_reminder_service = None  # type: ignore[assignment]
from backend.apps.admin_ui.utils import (
    norm_status,
    paginate,
    recruiter_time_to_utc,
    status_to_db,
)
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.models import City, Recruiter, Slot, SlotStatus, recruiter_city_association
from backend.domain.repositories import reject_slot

__all__ = [
    "list_slots",
    "recruiters_for_slot_form",
    "create_slot",
    "bulk_create_slots",
    "api_slots_payload",
    "delete_slot",
    "delete_all_slots",
    "set_slot_outcome",
    "get_state_manager",
    "execute_bot_dispatch",
    "reschedule_slot_booking",
    "reject_slot_booking",
]


logger = logging.getLogger(__name__)


DEFAULT_COMPANY_NAME = "SMART SERVICE"
DEFAULT_SLOT_TZ = "Europe/Moscow"
REJECTION_TEMPLATE_KEY = "result_fail"


def get_state_manager():
    """Compatibility wrapper exposing the bot state manager."""

    return _get_state_manager()


async def list_slots(
    recruiter_id: Optional[int],
    status: Optional[str],
    page: int,
    per_page: int,
) -> Dict[str, object]:
    async with async_session() as session:
        filtered = select(Slot)
        if recruiter_id is not None:
            filtered = filtered.where(Slot.recruiter_id == recruiter_id)
        if status:
            filtered = filtered.where(Slot.status == status_to_db(status))

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
            filtered.options(selectinload(Slot.recruiter))
            .order_by(Slot.start_utc.desc())
            .offset(offset)
            .limit(per_page)
        )
        items = (await session.scalars(query)).all()

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
    if has_active:
        query = query.where(getattr(Recruiter, "active") == True)  # noqa: E712
    async with async_session() as session:
        recs = (await session.scalars(query)).all()
        if not recs:
            return []
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
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            return False
        city = await session.get(City, city_id)
        if not city:
            return False
        allowed = await session.scalar(
            select(recruiter_city_association.c.city_id)
            .where(
                recruiter_city_association.c.recruiter_id == recruiter_id,
                recruiter_city_association.c.city_id == city_id,
            )
        )
        if allowed is None:
            return False
        dt_utc = recruiter_time_to_utc(date, time, getattr(recruiter, "tz", None))
        if not dt_utc:
            return False
        slot_tz = getattr(city, "tz", None) or getattr(recruiter, "tz", None) or DEFAULT_SLOT_TZ
        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value
        session.add(
            Slot(
                recruiter_id=recruiter_id,
                city_id=city_id,
                tz_name=slot_tz,
                start_utc=dt_utc,
                status=status_free,
            )
        )
        await session.commit()
        return True


async def delete_slot(
    slot_id: int, *, force: bool = False
) -> Tuple[bool, Optional[str]]:
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if not slot:
            return False, "Слот не найден"

        status = norm_status(slot.status)
        if not force and status not in {"FREE", "PENDING"}:
            return False, f"Нельзя удалить слот со статусом {status or 'UNKNOWN'}"

        await session.delete(slot)
        await session.commit()

    if callable(get_reminder_service):
        try:
            await get_reminder_service().cancel_for_slot(slot_id)
        except RuntimeError:
            pass

    return True, None


async def delete_all_slots(*, force: bool = False) -> Tuple[int, int]:
    async with async_session() as session:
        total_before = await session.scalar(select(func.count()).select_from(Slot)) or 0
        if total_before == 0:
            return 0, 0

        slot_ids: List[int] = []

        if force:
            result = await session.execute(select(Slot.id))
            slot_ids = [row[0] for row in result]
            await session.execute(delete(Slot))
            await session.commit()
            remaining_after = 0
        else:
            allowed_statuses = {
                status_to_db("FREE"),
                status_to_db("PENDING"),
            }
            result = await session.execute(
                select(Slot.id).where(Slot.status.in_(allowed_statuses))
            )
            slot_ids = [row[0] for row in result]
            if not slot_ids:
                return 0, total_before
            await session.execute(delete(Slot).where(Slot.id.in_(slot_ids)))
            await session.commit()
            remaining_after = (
                await session.scalar(select(func.count()).select_from(Slot)) or 0
            )

    if callable(get_reminder_service):
        for sid in slot_ids:
            try:
                await get_reminder_service().cancel_for_slot(sid)
            except RuntimeError:
                break

    deleted = total_before - remaining_after
    return deleted, remaining_after


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

    async with async_session() as session:
        slot = await session.scalar(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(Slot.id == slot_id)
        )
        if not slot:
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

    message = _format_outcome_message(normalized, dispatch.status if dispatch else None)
    reminder_service = None
    if callable(get_reminder_service):
        try:
            reminder_service = get_reminder_service()
        except RuntimeError:
            reminder_service = None
    if reminder_service is not None:
        if normalized == "success":
            await reminder_service.schedule_for_slot(slot_id)
        else:
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


async def reschedule_slot_booking(slot_id: int) -> Tuple[bool, str, bool]:
    async with async_session() as session:
        slot = await session.scalar(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(Slot.id == slot_id)
        )

    if not slot:
        return False, "Слот не найден.", False
    if slot.candidate_tg_id is None:
        return False, "Слот не привязан к кандидату.", False

    snapshot: SlotSnapshot = await capture_slot_snapshot(slot)
    await reject_slot(slot_id)
    await cancel_slot_reminders(slot_id)
    try:
        notification_service = get_notification_service()
    except RuntimeError:
        settings = get_settings()
        notification_service = NotificationService(
            poll_interval=settings.notification_poll_interval,
            batch_size=settings.notification_batch_size,
            rate_limit_per_sec=settings.notification_rate_limit_per_sec,
            max_attempts=settings.notification_max_attempts,
            retry_base_delay=settings.notification_retry_base_seconds,
            retry_max_delay=settings.notification_retry_max_seconds,
        )

    result = await notification_service.on_booking_status_changed(
        slot_id,
        BookingNotificationStatus.RESCHEDULE_REQUESTED,
        snapshot=snapshot,
    )

    if result.status == "sent":
        return True, "Слот освобождён. Кандидату отправлено уведомление о переносе.", True
    if result.status == "failed":
        return (
            True,
            "Слот освобождён. Бот недоступен — сообщите кандидату вручную.",
            False,
        )
    return (
        True,
        "Слот освобождён. Уведомление не отправлено.",
        False,
    )


async def reject_slot_booking(slot_id: int) -> Tuple[bool, str, bool]:
    async with async_session() as session:
        slot = await session.scalar(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(Slot.id == slot_id)
        )

    if not slot:
        return False, "Слот не найден.", False
    if slot.candidate_tg_id is None:
        return False, "Слот не привязан к кандидату.", False

    snapshot: SlotSnapshot = await capture_slot_snapshot(slot)
    await reject_slot(slot_id)
    await cancel_slot_reminders(slot_id)
    try:
        notification_service = get_notification_service()
    except RuntimeError:
        settings = get_settings()
        notification_service = NotificationService(
            poll_interval=settings.notification_poll_interval,
            batch_size=settings.notification_batch_size,
            rate_limit_per_sec=settings.notification_rate_limit_per_sec,
            max_attempts=settings.notification_max_attempts,
            retry_base_delay=settings.notification_retry_base_seconds,
            retry_max_delay=settings.notification_retry_max_seconds,
        )

    result = await notification_service.on_booking_status_changed(
        slot_id,
        BookingNotificationStatus.CANCELLED,
        snapshot=snapshot,
    )

    if result.status == "sent":
        return True, "Слот освобождён. Кандидату отправлен отказ.", True
    if result.status == "failed":
        return (
            True,
            "Слот освобождён. Сообщите кандидату об отказе вручную.",
            False,
        )
    return (
        True,
        "Слот освобождён. Уведомление не отправлено.",
        False,
    )



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
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            return 0, "Рекрутёр не найден"

        city = await session.get(City, city_id)
        if not city:
            return 0, "Город не найден"
        allowed = await session.scalar(
            select(recruiter_city_association.c.city_id)
            .where(
                recruiter_city_association.c.recruiter_id == recruiter_id,
                recruiter_city_association.c.city_id == city_id,
            )
        )
        if allowed is None:
            return 0, "Город не привязан к выбранному рекрутёру"

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
        if step_min <= 0:
            return 0, "Шаг должен быть положительным"

        if use_break and pause_end <= pause_start:
            return 0, "Время окончания перерыва должно быть позже его начала"

        start_minutes = window_start.hour * 60 + window_start.minute
        end_minutes = window_end.hour * 60 + window_end.minute
        break_start_minutes = pause_start.hour * 60 + pause_start.minute
        break_end_minutes = pause_end.hour * 60 + pause_end.minute

        tz = getattr(recruiter, "tz", None)
        city_tz = getattr(city, "tz", None)
        slot_tz = city_tz or tz or DEFAULT_SLOT_TZ

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
                    dt_utc = recruiter_time_to_utc(
                        current_date.isoformat(), time_str, tz
                    )
                    if not dt_utc:
                        return 0, "Не удалось преобразовать время в UTC"
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
                    start_utc=dt,
                    status=status_free,
                    duration_min=max(step_min, 1),
                    tz_name=slot_tz,
                )
                for dt in to_insert
            ]
        )
        await session.commit()
        return len(to_insert), None


def _format_slot_local_time(slot: Slot) -> str:
    tz_label = getattr(slot, "tz_name", None) or DEFAULT_SLOT_TZ
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
            .options(selectinload(Slot.recruiter))
            .order_by(Slot.start_utc.asc())
        )
        if recruiter_id is not None:
            query = query.where(Slot.recruiter_id == recruiter_id)
        if status:
            query = query.where(Slot.status == status_to_db(status))
        if limit:
            query = query.limit(max(1, min(500, limit)))
        slots = (await session.scalars(query)).all()
    return [
        {
            "id": sl.id,
            "recruiter_id": sl.recruiter_id,
            "recruiter_name": sl.recruiter.name if sl.recruiter else None,
            "start_utc": sl.start_utc.isoformat(),
            "status": norm_status(sl.status),
            "candidate_fio": getattr(sl, "candidate_fio", None),
            "candidate_tg_id": getattr(sl, "candidate_tg_id", None),
            "tz_name": getattr(sl, "tz_name", None),
            "local_time": _format_slot_local_time(sl),
        }
        for sl in slots
    ]
