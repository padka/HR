from __future__ import annotations

import logging
import sys
from typing import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from datetime import time as time_type

from sqlalchemy import delete, func, select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.services.bot_service import (
    BotSendResult,
    BotService,
)
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
)
from backend.apps.bot.services import (
    get_state_manager as _get_state_manager,
)

try:  # pragma: no cover - optional dependency during tests
    from backend.apps.bot.reminders import get_reminder_service
except Exception:  # pragma: no cover - safe fallback when bot package unavailable
    get_reminder_service = None  # type: ignore[assignment]
from backend.apps.admin_ui.utils import (
    local_naive_to_utc,
    norm_status,
    paginate,
    status_to_db,
    validate_timezone_name,
)
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.models import City, Recruiter, Slot, SlotStatus
from backend.domain.repositories import reject_slot

__all__ = [
    "list_slots",
    "recruiters_for_slot_form",
    "create_slot",
    "bulk_create_slots",
    "api_slots_payload",
    "delete_slot",
    "delete_all_slots",
    "bulk_assign_slots",
    "bulk_schedule_reminders",
    "bulk_delete_slots",
    "set_slot_outcome",
    "get_state_manager",
    "execute_bot_dispatch",
    "reschedule_slot_booking",
    "reject_slot_booking",
]


logger = logging.getLogger(__name__)


DEFAULT_COMPANY_NAME = "SMART SERVICE"
REJECTION_TEMPLATE_KEY = "result_fail"


def get_state_manager():
    """Compatibility wrapper exposing the bot state manager."""

    return _get_state_manager()


async def list_slots(
    recruiter_id: int | None,
    status: str | None,
    page: int,
    per_page: int,
    *,
    city_id: int | None = None,
) -> dict[str, object]:
    async with async_session() as session:
        filtered = select(Slot)
        if recruiter_id is not None:
            filtered = filtered.where(Slot.recruiter_id == recruiter_id)
        if status:
            filtered = filtered.where(Slot.status == status_to_db(status))
        if city_id is not None:
            filtered = filtered.where(Slot.city_id == city_id)

        subquery = filtered.subquery()
        total = await session.scalar(select(func.count()).select_from(subquery)) or 0

        status_rows = (
            await session.execute(
                select(subquery.c.status, func.count())
                .select_from(subquery)
                .group_by(subquery.c.status)
            )
        ).all()

        aggregated: dict[str, int] = {}
        for raw_status, count in status_rows:
            aggregated[norm_status(raw_status)] = int(count or 0)
        aggregated.setdefault("CONFIRMED_BY_CANDIDATE", 0)

        pages_total, page, offset = paginate(total, page, per_page)

        query = (
            filtered.options(selectinload(Slot.recruiter), selectinload(Slot.city))
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


async def recruiters_for_slot_form() -> list[dict[str, object]]:
    inspector = sa_inspect(Recruiter)
    has_active = "active" in getattr(inspector, "columns", {})
    query = select(Recruiter).order_by(Recruiter.name.asc())
    if has_active:
        query = query.where(Recruiter.active == True)  # noqa: E712
    async with async_session() as session:
        recs = (await session.scalars(query)).all()
        if not recs:
            return []

        rec_ids = [rec.id for rec in recs]
        city_rows = (
            await session.scalars(
                select(City)
                .where(City.responsible_recruiter_id.in_(rec_ids))
                .order_by(City.name.asc())
            )
        ).all()

        city_map: dict[int, list[City]] = {}
        for city in city_rows:
            if city.responsible_recruiter_id is None:
                continue
            city_map.setdefault(city.responsible_recruiter_id, []).append(city)

    return [{"rec": rec, "cities": city_map.get(rec.id, [])} for rec in recs]


async def create_slot(
    recruiter_id: int,
    date: str,
    time: str,
    *,
    city_id: int,
) -> tuple[bool, Slot | None]:
    try:
        local_dt = datetime.fromisoformat(f"{date}T{time}")
    except ValueError:
        return False, None

    async with async_session() as session:
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            return False, None
        city = await session.get(City, city_id)
        if not city or city.responsible_recruiter_id != recruiter_id:
            return False, None
        try:
            tz_name = validate_timezone_name(city.tz)
        except ValueError:
            return False, None

        dt_utc = local_naive_to_utc(local_dt, tz_name)
        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value

        slot = Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            start_utc=dt_utc,
            status=status_free,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        return True, slot


async def delete_slot(slot_id: int, *, force: bool = False) -> tuple[bool, str | None]:
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


async def delete_all_slots(*, force: bool = False) -> tuple[int, int]:
    async with async_session() as session:
        total_before = await session.scalar(select(func.count()).select_from(Slot)) or 0
        if total_before == 0:
            return 0, 0

        slot_ids: list[int] = []

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


async def bulk_assign_slots(slot_ids: list[int], recruiter_id: int) -> tuple[int, list[int]]:
    if not slot_ids:
        return 0, []

    async with async_session() as session:
        recruiter = await session.get(Recruiter, recruiter_id)
        if recruiter is None:
            raise ValueError("Рекрутёр не найден")

        slots = (
            await session.scalars(select(Slot).where(Slot.id.in_(slot_ids)))
        ).all()
        found_ids = {slot.id for slot in slots}

        if not slots:
            return 0, list(slot_ids)

        for slot in slots:
            slot.recruiter_id = recruiter_id

        await session.commit()

    missing = [sid for sid in slot_ids if sid not in found_ids]
    return len(slots), missing


async def bulk_schedule_reminders(slot_ids: list[int]) -> tuple[int, list[int]]:
    if not slot_ids:
        return 0, []

    if not callable(get_reminder_service):
        raise RuntimeError("Сервис напоминаний недоступен")

    reminder_service = get_reminder_service()
    scheduled = 0
    failed: list[int] = []

    async with async_session() as session:
        existing_ids = set(
            await session.scalars(select(Slot.id).where(Slot.id.in_(slot_ids)))
        )

    for slot_id in slot_ids:
        if slot_id not in existing_ids:
            failed.append(slot_id)
            continue
        try:
            await reminder_service.schedule_for_slot(slot_id)
        except Exception:
            failed.append(slot_id)
        else:
            scheduled += 1

    return scheduled, failed


async def bulk_delete_slots(slot_ids: list[int], *, force: bool = False) -> tuple[int, list[int]]:
    if not slot_ids:
        return 0, []

    deleted = 0
    failed: list[int] = []

    for slot_id in slot_ids:
        ok, _ = await delete_slot(slot_id, force=force)
        if ok:
            deleted += 1
        else:
            failed.append(slot_id)

    return deleted, failed


@dataclass
class BotDispatchPlan:
    kind: str
    slot_id: int
    candidate_id: int
    candidate_tz: str | None = None
    candidate_city_id: int | None = None
    candidate_name: str = ""
    recruiter_name: str | None = None
    template_key: str | None = None
    template_context: dict[str, object] = field(default_factory=dict)
    scheduled_at: datetime | None = None
    required: bool | None = None


@dataclass
class BotDispatch:
    status: str
    plan: BotDispatchPlan | None = None


async def set_slot_outcome(
    slot_id: int,
    outcome: str,
    *,
    bot_service: BotService | None = None,
) -> tuple[bool, str | None, str | None, BotDispatch | None]:
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

        dispatch: BotDispatch | None
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


def _plan_test2_dispatch(slot: Slot, service: BotService | None) -> BotDispatch:
    if slot.test2_sent_at is not None:
        return BotDispatch(status="skipped:already_sent")

    if service is None:
        return BotDispatch(status="skipped:not_configured")

    if not service.enabled:
        return BotDispatch(status="skipped:disabled")

    if not service.is_ready():
        return BotDispatch(status="skipped:not_configured")

    scheduled_at = datetime.now(UTC)
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


def _plan_rejection_dispatch(slot: Slot, service: BotService | None) -> BotDispatch:
    if slot.rejection_sent_at is not None:
        return BotDispatch(status="skipped:already_sent")

    if service is None:
        return BotDispatch(status="skipped:not_configured")

    if not service.enabled:
        return BotDispatch(status="skipped:disabled")

    if not service.is_ready():
        return BotDispatch(status="skipped:not_configured")

    scheduled_at = datetime.now(UTC)
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
            "city_name": slot.city.name if slot.city else "",
            "recruiter_name": slot.recruiter.name if slot.recruiter else "",
        },
        scheduled_at=scheduled_at,
    )
    return BotDispatch(status="sent_rejection", plan=plan)


def _format_outcome_message(outcome: str, status: str | None) -> str:
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
            trigger_test2 = _resolve_trigger("_trigger_test2", _trigger_test2)
            result = await trigger_test2(
                plan.candidate_id,
                plan.candidate_tz,
                plan.candidate_city_id,
                plan.candidate_name,
                bot_service=service,
                required=plan.required,
            )
            action_result = _map_test2_status(result.status)
            success = result.ok and action_result == "sent_test2"
        elif plan.kind == "rejection":
            trigger_rejection = _resolve_trigger(
                "_trigger_rejection", _trigger_rejection
            )
            result = await trigger_rejection(
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


def _resolve_trigger(
    name: str,
    fallback: Callable[..., Awaitable[BotSendResult]],
) -> Callable[..., Awaitable[BotSendResult]]:
    module = sys.modules.get("backend.apps.admin_ui.services.slots")
    if module is not None:
        candidate = getattr(module, name, None)
        if callable(candidate):
            return candidate
    return fallback


async def _mark_dispatch_state(slot_id: int, kind: str, success: bool) -> None:
    field = "test2_sent_at" if kind == "test2" else "rejection_sent_at"
    async with async_session() as session:
        slot = await session.get(Slot, slot_id)
        if not slot:
            return
        if success:
            setattr(slot, field, datetime.now(UTC))
        else:
            setattr(slot, field, None)
        await session.commit()


async def _trigger_test2(
    candidate_id: int,
    candidate_tz: str | None,
    candidate_city: int | None,
    candidate_name: str,
    *,
    bot_service: BotService | None,
    required: bool,
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
    )


async def reschedule_slot_booking(slot_id: int) -> tuple[bool, str, bool]:
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
        notification_service = NotificationService()

    result = await notification_service.on_booking_status_changed(
        slot_id,
        BookingNotificationStatus.RESCHEDULE_REQUESTED,
        snapshot=snapshot,
    )

    if result.status == "sent":
        return (
            True,
            "Слот освобождён. Кандидату отправлено уведомление о переносе.",
            True,
        )
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


async def reject_slot_booking(slot_id: int) -> tuple[bool, str, bool]:
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
        notification_service = NotificationService()

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
    context: dict[str, object],
    *,
    city_id: int | None,
    bot_service: BotService | None,
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
    return dt.astimezone(UTC).replace(tzinfo=None)


def _as_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware UTC for database comparisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


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
) -> tuple[int, str | None]:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            return 0, "Рекрутёр не найден"

        city = await session.get(City, city_id)
        if not city:
            return 0, "Город не найден"
        if city.responsible_recruiter_id != recruiter_id:
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

        try:
            tz = validate_timezone_name(city.tz)
        except ValueError:
            return 0, "Некорректный часовой пояс региона"

        planned_pairs: list[tuple[datetime, datetime]] = []  # (original, normalized)
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
                    try:
                        dt_local = datetime.fromisoformat(
                            f"{current_date.isoformat()}T{time_str}"
                        )
                    except ValueError:
                        return 0, "Некорректное время"
                    dt_utc = local_naive_to_utc(dt_local, tz)
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
                )
                for dt in to_insert
            ]
        )
        await session.commit()
        return len(to_insert), None


async def api_slots_payload(
    recruiter_id: int | None,
    status: str | None,
    limit: int,
) -> list[dict[str, object]]:
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
        }
        for sl in slots
    ]
