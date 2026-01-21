from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.services.bot_service import BotSendResult, BotService
from backend.apps.admin_ui.services.bot_service import (
    get_bot_service as resolve_bot_service,
)
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.models import Slot
from backend.domain.repositories import reject_slot

try:  # pragma: no cover - optional dependency during tests
    from backend.apps.bot.reminders import get_reminder_service
except Exception:  # pragma: no cover - safe fallback when bot package unavailable
    get_reminder_service = None  # type: ignore[assignment]

from backend.apps.bot.services import (
    BookingNotificationStatus,
    NotificationService,
    SlotSnapshot,
    cancel_slot_reminders,
    capture_slot_snapshot,
    get_notification_service,
    get_state_manager as _get_state_manager,
)

logger = logging.getLogger(__name__)


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


def get_state_manager():
    """Compatibility wrapper exposing the bot state manager."""

    return _get_state_manager()


async def set_slot_outcome(
    slot_id: int,
    outcome: str,
    *,
    bot_service: Optional[BotService] = None,
) -> tuple[bool, Optional[str], Optional[str], Optional[BotDispatch]]:
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

    settings = get_settings()
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
        template_key=settings.rejection_template_key,
        template_context={
            "candidate_fio": getattr(slot, "candidate_fio", "") or "",
            "company_name": settings.default_company_name,
            "city_name": slot.city.name if slot.city else "",
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
        slots_pkg = sys.modules.get("backend.apps.admin_ui.services.slots")
        trigger_test2 = getattr(slots_pkg, "_trigger_test2", _trigger_test2) if slots_pkg else _trigger_test2
        trigger_rejection = (
            getattr(slots_pkg, "_trigger_rejection", _trigger_rejection) if slots_pkg else _trigger_rejection
        )

        if plan.kind == "test2":
            try:
                result = await trigger_test2(
                    plan.candidate_id,
                    plan.candidate_tz,
                    plan.candidate_city_id,
                    plan.candidate_name,
                    bot_service=service,
                    required=plan.required,
                    slot_id=plan.slot_id,
                )
            except TypeError:
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
            result = await trigger_rejection(
                plan.candidate_id,
                plan.template_key or get_settings().rejection_template_key,
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
