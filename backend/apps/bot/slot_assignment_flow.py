"""Slot assignment dialog handlers for candidate callbacks and datetime input."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, ForceReply, Message
from sqlalchemy import select

from backend.apps.bot.backend_client import BackendClient, BackendClientError
from backend.apps.bot.config import DEFAULT_TZ, TIME_FMT
from backend.apps.bot.keyboards import (
    kb_slot_assignment_reschedule_options,
)
from backend.apps.bot.security import verify_callback_data
from backend.apps.bot.services import (
    _format_manual_window_label,
    _parse_manual_availability_window,
    build_candidate_active_meeting_keyboard,
    get_candidate_assignment_controls,
    get_bot,
    get_state_manager,
    render_candidate_assignment_details,
)
from backend.apps.bot.utils.text import escape_html
from backend.core.db import async_session
from backend.domain.models import Slot, SlotAssignment
from backend.domain.repositories import add_message_log, get_free_slots_by_recruiter
from backend.domain.slot_assignment_service import begin_reschedule_request

STATE_WAITING_DATETIME = "waiting_candidate_datetime_input"
RESCHEDULE_PICK_PREFIX = "slotres:pick:"
RESCHEDULE_MANUAL_PREFIX = "slotres:manual:"
DETAILS_PREFIX = "slotasg:details:"
LEGACY_CONFIRM_PREFIX = "confirm_assignment:"
LEGACY_RESCHEDULE_PREFIX = "reschedule_assignment:"
LEGACY_DECLINE_PREFIX = "decline_assignment:"

WORKDAY_START = time(9, 0)
WORKDAY_END = time(20, 0)
MAX_DAYS_AHEAD = 60
MINUTE_STEP = 15


logger = logging.getLogger(__name__)


def _safe_zone(tz_name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def _parse_payload(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    raw = raw.strip()
    if not raw.startswith("{"):
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    action = data.get("action") or data.get("a")
    assignment_id = data.get("slot_assignment_id") or data.get("i")
    token = data.get("action_token") or data.get("t")
    if not action or assignment_id is None or not token:
        return None
    try:
        assignment_id_int = int(assignment_id)
    except (TypeError, ValueError):
        return None
    return {
        "action": str(action),
        "slot_assignment_id": assignment_id_int,
        "action_token": str(token),
    }


def _normalize_purpose(value: Optional[str]) -> str:
    return (value or "interview").strip().lower() or "interview"


def _manual_prompt_text() -> str:
    return (
        "Напишите желаемую дату и время. Можно указать точный слот или диапазон.\n"
        "Примеры: «12.03 14:00», «12.03 14:00-18:00», «завтра 10:00-13:00».\n"
        "Если точное время неизвестно, просто напишите удобный вариант в свободной форме."
    )


async def _get_assignment_context(assignment_id: int) -> tuple[Optional[SlotAssignment], Optional[Slot], list[Slot]]:
    async with async_session() as session:
        assignment = await session.scalar(select(SlotAssignment).where(SlotAssignment.id == assignment_id))
        if assignment is None:
            return None, None, []
        slot = await session.scalar(select(Slot).where(Slot.id == assignment.slot_id))
        if slot is None:
            return assignment, None, []

    slots = await get_free_slots_by_recruiter(assignment.recruiter_id, city_id=slot.city_id)
    source_purpose = _normalize_purpose(slot.purpose)
    alternatives = [
        item
        for item in slots
        if item.id != slot.id and _normalize_purpose(getattr(item, "purpose", None)) == source_purpose
    ]
    return assignment, slot, alternatives


async def _prompt_manual_entry(
    *,
    candidate_id: int,
    assignment_id: int,
    action_token: str,
    candidate_tz: str,
) -> None:
    state_manager = get_state_manager()
    await state_manager.update(
        candidate_id,
        {
            "slot_assignment_state": STATE_WAITING_DATETIME,
            "slot_assignment_id": assignment_id,
            "slot_assignment_action_token": action_token,
            "slot_assignment_candidate_tz": candidate_tz,
        },
    )
    bot = get_bot()
    await bot.send_message(candidate_id, _manual_prompt_text())


async def handle_reschedule_choice_callback(callback: CallbackQuery) -> bool:
    raw = callback.data or ""
    if raw.startswith(RESCHEDULE_PICK_PREFIX):
        return await _handle_reschedule_slot_pick(callback)
    if raw.startswith(RESCHEDULE_MANUAL_PREFIX):
        return await _handle_reschedule_manual(callback)
    return False


async def handle_slot_assignment_callback(callback: CallbackQuery) -> bool:
    payload = _parse_payload(callback.data)
    if not payload:
        return False

    user = callback.from_user
    if user is None:
        await callback.answer()
        return True

    action = payload["action"]
    assignment_id = payload["slot_assignment_id"]
    action_token = payload["action_token"]
    candidate_id = user.id

    if action == "confirm":
        await _handle_confirm(callback, assignment_id, action_token, candidate_id)
        return True
    if action == "reschedule":
        await _handle_reschedule_prompt(callback, assignment_id, action_token, candidate_id)
        return True
    if action == "decline":
        await _handle_decline(callback, assignment_id, action_token, candidate_id)
        return True

    await callback.answer("Неизвестное действие", show_alert=True)
    return True


async def handle_assignment_details_callback(callback: CallbackQuery) -> bool:
    payload = verify_callback_data(callback.data or "", expected_prefix=DETAILS_PREFIX)
    if not payload:
        await callback.answer("Ссылка устарела. Откройте детали встречи заново.", show_alert=True)
        return True

    try:
        assignment_id = int(payload.split(":", 2)[2])
    except (IndexError, ValueError):
        await callback.answer("Некорректный запрос.", show_alert=True)
        return True

    user = callback.from_user
    if user is None:
        await callback.answer()
        return True

    controls = await get_candidate_assignment_controls(
        candidate_tg_id=int(user.id),
        assignment_id=assignment_id,
    )
    if controls is None:
        await callback.answer("Встреча не найдена или уже недоступна.", show_alert=True)
        return True

    await callback.answer()
    await get_bot().send_message(
        user.id,
        render_candidate_assignment_details(controls),
        reply_markup=build_candidate_active_meeting_keyboard(controls),
    )
    return True


async def handle_legacy_assignment_callback(callback: CallbackQuery) -> bool:
    raw = callback.data or ""
    if raw.startswith(LEGACY_CONFIRM_PREFIX):
        action = "confirm"
        prefix = LEGACY_CONFIRM_PREFIX
    elif raw.startswith(LEGACY_RESCHEDULE_PREFIX):
        action = "reschedule"
        prefix = LEGACY_RESCHEDULE_PREFIX
    elif raw.startswith(LEGACY_DECLINE_PREFIX):
        action = "decline"
        prefix = LEGACY_DECLINE_PREFIX
    else:
        return False

    try:
        assignment_id = int(raw.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректный запрос.", show_alert=True)
        return True

    user = callback.from_user
    if user is None:
        await callback.answer()
        return True

    controls = await get_candidate_assignment_controls(
        candidate_tg_id=int(user.id),
        assignment_id=assignment_id,
    )
    if controls is None:
        await callback.answer("Назначение не найдено или уже недоступно.", show_alert=True)
        return True

    if action == "confirm" and controls.confirm_token:
        await _handle_confirm(callback, assignment_id, controls.confirm_token, int(user.id))
        return True
    if action == "reschedule" and controls.reschedule_token:
        await _handle_reschedule_prompt(callback, assignment_id, controls.reschedule_token, int(user.id))
        return True
    if action == "decline" and controls.decline_token:
        await _handle_decline(callback, assignment_id, controls.decline_token, int(user.id))
        return True

    await callback.answer("Действие больше недоступно.", show_alert=True)
    return True


async def _handle_confirm(
    callback: CallbackQuery,
    assignment_id: int,
    action_token: str,
    candidate_id: int,
) -> None:
    client = BackendClient()
    if not client.configured:
        await callback.answer("Сервис временно недоступен", show_alert=True)
        return

    try:
        status, data = await client.post_json(
            f"/api/slot-assignments/{assignment_id}/confirm",
            {
                "action_token": action_token,
                "candidate_tg_id": candidate_id,
            },
        )
    except BackendClientError as exc:
        logger.warning(
            "slot_assignment.confirm.backend_unavailable assignment_id=%s candidate_tg_id=%s error=%s",
            assignment_id,
            candidate_id,
            exc,
        )
        await callback.answer("Сервис недоступен. Попробуйте позже.", show_alert=True)
        return

    if status == 409:
        detail = data.get("detail") if isinstance(data, dict) else None
        await callback.answer(detail or "Слот уже занят или ссылка устарела.", show_alert=True)
        return
    if status >= 400:
        detail = data.get("detail") if isinstance(data, dict) else None
        await callback.answer(detail or "Не удалось подтвердить слот.", show_alert=True)
        return

    state_manager = get_state_manager()
    await state_manager.update(
        candidate_id,
        {
            "slot_assignment_state": "confirmed",
            "slot_assignment_id": assignment_id,
        },
    )

    try:
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await callback.answer("Время подтверждено")


async def _handle_reschedule_prompt(
    callback: CallbackQuery,
    assignment_id: int,
    action_token: str,
    candidate_id: int,
) -> None:
    result = await begin_reschedule_request(
        assignment_id=assignment_id,
        action_token=action_token,
        candidate_tg_id=candidate_id,
    )
    if not result.ok:
        await callback.answer(result.message or "Не удалось запросить другое время.", show_alert=True)
        return

    await callback.answer()
    try:
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    state_manager = get_state_manager()
    state = await state_manager.get(candidate_id) or {}
    assignment, slot, alternatives = await _get_assignment_context(assignment_id)
    candidate_tz = (
        state.get("slot_assignment_candidate_tz")
        or state.get("candidate_tz")
        or (assignment.candidate_tz if assignment else None)
        or (slot.candidate_tz if slot else None)
        or DEFAULT_TZ
    )

    await state_manager.update(
        candidate_id,
        {
            "slot_assignment_state": STATE_WAITING_DATETIME,
            "slot_assignment_id": assignment_id,
            "slot_assignment_action_token": action_token,
            "slot_assignment_candidate_tz": candidate_tz,
        },
    )

    bot = get_bot()
    if alternatives:
        await bot.send_message(
            candidate_id,
            "Могу предложить ближайшие свободные варианты. Если ничего не подходит, нажмите «Написать вручную».",
            reply_markup=kb_slot_assignment_reschedule_options(
                assignment_id,
                candidate_tz=candidate_tz,
                slots=alternatives,
            ),
        )
        return

    await bot.send_message(
        candidate_id,
        "Свободных слотов на сейчас не вижу.",
    )
    await _prompt_manual_entry(
        candidate_id=candidate_id,
        assignment_id=assignment_id,
        action_token=action_token,
        candidate_tz=candidate_tz,
    )


async def _handle_decline(
    callback: CallbackQuery,
    assignment_id: int,
    action_token: str,
    candidate_id: int,
) -> None:
    controls = await get_candidate_assignment_controls(
        candidate_tg_id=int(candidate_id),
        assignment_id=assignment_id,
    )
    client = BackendClient()
    if not client.configured:
        await callback.answer("Сервис временно недоступен", show_alert=True)
        return

    try:
        status, data = await client.post_json(
            f"/api/slot-assignments/{assignment_id}/decline",
            {
                "action_token": action_token,
                "candidate_tg_id": candidate_id,
            },
        )
    except BackendClientError as exc:
        logger.warning(
            "slot_assignment.decline.backend_unavailable assignment_id=%s candidate_tg_id=%s error=%s",
            assignment_id,
            candidate_id,
            exc,
        )
        await callback.answer("Сервис недоступен. Попробуйте позже.", show_alert=True)
        return

    if status == 409:
        detail = data.get("detail") if isinstance(data, dict) else None
        await callback.answer(detail or "Действие недоступно.", show_alert=True)
        return
    if status >= 400:
        detail = data.get("detail") if isinstance(data, dict) else None
        await callback.answer(detail or "Не удалось оформить отказ.", show_alert=True)
        return

    state_manager = get_state_manager()
    await state_manager.update(
        candidate_id,
        {
            "slot_assignment_state": "declined",
            "slot_assignment_id": assignment_id,
        },
    )

    try:
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await callback.answer("Отказ принят")
    bot = get_bot()
    message_text = data.get("message") if isinstance(data, dict) else None
    prompt = (
        "Напишите, пожалуйста, коротко причину отмены, чтобы мы сразу передали её рекрутёру."
    )
    await get_state_manager().update(
        candidate_id,
        {
            "awaiting_slot_assignment_decline_reason": {
                "assignment_id": assignment_id,
                "slot_id": controls.slot_id if controls else None,
                "recruiter_chat_id": controls.recruiter_tg_id if controls else None,
                "recruiter_name": controls.recruiter_name if controls else "",
                "candidate_name": controls.candidate_name if controls else "",
                "start_local": (
                    controls.start_utc.astimezone(_safe_zone(controls.candidate_tz)).strftime(TIME_FMT)
                    if controls is not None
                    else ""
                ),
            },
            "slot_assignment_state": "declined",
            "slot_assignment_id": assignment_id,
        },
    )
    await bot.send_message(
        candidate_id,
        message_text or "Мы зафиксировали отказ. Спасибо за ответ.",
    )
    await bot.send_message(
        candidate_id,
        prompt,
        reply_markup=ForceReply(selective=True),
    )


async def capture_slot_assignment_decline_reason(message: Message, state: Dict[str, Any]) -> bool:
    reason_payload = state.get("awaiting_slot_assignment_decline_reason") or {}
    assignment_id = reason_payload.get("assignment_id")
    if not assignment_id:
        return False

    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Напишите, пожалуйста, коротко причину отмены.")
        return True

    recruiter_chat_id = reason_payload.get("recruiter_chat_id")
    candidate_name = reason_payload.get("candidate_name") or str(message.from_user.id if message.from_user else "")
    start_local = reason_payload.get("start_local") or ""
    recruiter_note_sent = False
    if recruiter_chat_id:
        recruiter_text = (
            "⛔️ Кандидат отменил встречу.\n"
            f"👤 {escape_html(str(candidate_name))}\n"
            f"🗓 {escape_html(str(start_local))}\n"
            f"Причина: {escape_html(text)}"
        )
        try:
            await get_bot().send_message(int(recruiter_chat_id), recruiter_text)
            recruiter_note_sent = True
        except Exception:
            logger.exception(
                "slot_assignment.decline_reason.forward_failed",
                extra={"assignment_id": assignment_id, "recruiter_chat_id": recruiter_chat_id},
            )

    try:
        await add_message_log(
            "slot_assignment_decline_reason",
            recipient_type="candidate",
            recipient_id=message.from_user.id if message.from_user else 0,
            slot_assignment_id=int(assignment_id),
            payload={"reason": text, "recruiter_notified": recruiter_note_sent},
        )
    except Exception:
        logger.exception(
            "slot_assignment.decline_reason.log_failed",
            extra={"assignment_id": assignment_id},
        )

    await message.answer("Спасибо, передали информацию рекрутеру." if recruiter_note_sent else "Спасибо, получили причину отмены.")

    try:
        state_manager = get_state_manager()

        def _clear(st):
            current = dict(st or {})
            current.pop("awaiting_slot_assignment_decline_reason", None)
            return current, None

        if message.from_user is not None:
            await state_manager.atomic_update(message.from_user.id, _clear)
    except Exception:
        logger.exception(
            "slot_assignment.decline_reason.state_clear_failed",
            extra={"assignment_id": assignment_id},
        )

    return True


async def _handle_reschedule_manual(callback: CallbackQuery) -> bool:
    payload = verify_callback_data(callback.data or "", expected_prefix=RESCHEDULE_MANUAL_PREFIX)
    if not payload:
        await callback.answer("Ссылка устарела. Нажмите «Другое время» ещё раз.", show_alert=True)
        return True

    try:
        assignment_id = int(payload.split(":", 2)[2])
    except (IndexError, ValueError):
        await callback.answer("Некорректный запрос.", show_alert=True)
        return True

    user = callback.from_user
    if user is None:
        await callback.answer()
        return True

    state = await get_state_manager().get(user.id) or {}
    action_token = state.get("slot_assignment_action_token")
    if not action_token or int(state.get("slot_assignment_id") or 0) != assignment_id:
        await callback.answer("Сессия устарела. Запросите перенос ещё раз.", show_alert=True)
        return True

    await callback.answer()
    try:
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    candidate_tz = state.get("slot_assignment_candidate_tz") or state.get("candidate_tz") or DEFAULT_TZ
    await _prompt_manual_entry(
        candidate_id=user.id,
        assignment_id=assignment_id,
        action_token=action_token,
        candidate_tz=candidate_tz,
    )
    return True


async def _handle_reschedule_slot_pick(callback: CallbackQuery) -> bool:
    payload = verify_callback_data(callback.data or "", expected_prefix=RESCHEDULE_PICK_PREFIX)
    if not payload:
        await callback.answer("Ссылка устарела. Нажмите «Другое время» ещё раз.", show_alert=True)
        return True

    parts = payload.split(":", 3)
    if len(parts) != 4:
        await callback.answer("Некорректный запрос.", show_alert=True)
        return True
    try:
        assignment_id = int(parts[2])
        slot_id = int(parts[3])
    except ValueError:
        await callback.answer("Некорректный слот.", show_alert=True)
        return True

    user = callback.from_user
    if user is None:
        await callback.answer()
        return True

    state_manager = get_state_manager()
    state = await state_manager.get(user.id) or {}
    action_token = state.get("slot_assignment_action_token")
    if not action_token or int(state.get("slot_assignment_id") or 0) != assignment_id:
        await callback.answer("Сессия устарела. Запросите перенос ещё раз.", show_alert=True)
        return True

    async with async_session() as session:
        target_slot = await session.scalar(select(Slot).where(Slot.id == slot_id))
    if target_slot is None or target_slot.start_utc is None:
        await callback.answer("Слот не найден. Попробуйте ещё раз.", show_alert=True)
        return True

    candidate_tz = state.get("slot_assignment_candidate_tz") or state.get("candidate_tz") or DEFAULT_TZ
    client = BackendClient()
    if not client.configured:
        await callback.answer("Сервис временно недоступен", show_alert=True)
        return True

    try:
        status, data = await client.post_json(
            f"/api/slot-assignments/{assignment_id}/request-reschedule",
            {
                "action_token": action_token,
                "candidate_tg_id": user.id,
                "requested_start_utc": target_slot.start_utc.astimezone(timezone.utc).isoformat(),
                "requested_tz": candidate_tz,
                "comment": None,
            },
        )
    except BackendClientError as exc:
        logger.warning(
            "slot_assignment.request_reschedule.slot_pick.backend_unavailable assignment_id=%s candidate_tg_id=%s error=%s",
            assignment_id,
            user.id,
            exc,
        )
        await callback.answer("Сервис недоступен. Попробуйте позже.", show_alert=True)
        return True

    if status >= 400:
        detail = data.get("detail") if isinstance(data, dict) else None
        await callback.answer(detail or "Не удалось отправить запрос.", show_alert=True)
        return True

    await state_manager.update(
        user.id,
        {
            "slot_assignment_state": "reschedule_pending",
            "slot_assignment_id": assignment_id,
            "slot_assignment_action_token": None,
        },
    )

    await callback.answer("Запрос отправлен")
    try:
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await get_bot().send_message(
        user.id,
        f"Запросили новое время: {target_slot.start_utc.astimezone(_safe_zone(candidate_tz)).strftime(TIME_FMT)}. Мы сообщим ответ рекрутёра.",
    )
    return True


def _parse_datetime_input(text: str, tz_name: Optional[str]) -> Optional[datetime]:
    value = (text or "").strip()
    if not value:
        return None

    time_matches = list(re.finditer(r"(\d{1,2})\s*[:.]\s*(\d{2})", value))
    if not time_matches:
        return None

    time_match = time_matches[-1]
    try:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
    except ValueError:
        return None

    if hour > 23 or minute > 59:
        return None

    time_span = time_match.span()
    date_match = None
    for match in re.finditer(r"(\d{1,2})\s*[./-]\s*(\d{1,2})(?:\s*[./-]\s*(\d{2,4}))?", value):
        span = match.span()
        if span[1] <= time_span[0] or span[0] >= time_span[1]:
            date_match = match
            break

    zone = _safe_zone(tz_name)
    now_local = datetime.now(zone)

    lowered = value.lower()
    relative_days = 0
    if "послезавтра" in lowered:
        relative_days = 2
    elif "завтра" in lowered:
        relative_days = 1
    elif "сегодня" in lowered:
        relative_days = 0

    if date_match:
        try:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
        except ValueError:
            return None

        year_raw = date_match.group(3)
        if year_raw:
            try:
                year = int(year_raw)
            except ValueError:
                return None
            if year < 100:
                year += 2000
        else:
            year = now_local.year

        try:
            candidate_dt = datetime(year, month, day, hour, minute, tzinfo=zone)
        except ValueError:
            return None

        if candidate_dt < now_local:
            return None
        return candidate_dt

    base_date = now_local.date() + timedelta(days=relative_days)
    candidate_dt = datetime(
        base_date.year,
        base_date.month,
        base_date.day,
        hour,
        minute,
        tzinfo=zone,
    )
    if candidate_dt < now_local:
        candidate_dt = candidate_dt + timedelta(days=1)
    return candidate_dt


async def handle_datetime_input(message: Message, state: Dict[str, Any]) -> bool:
    if state.get("slot_assignment_state") != STATE_WAITING_DATETIME:
        return False

    user = message.from_user
    if user is None:
        return False

    candidate_id = user.id
    text = (message.text or message.caption or "").strip()
    candidate_tz = state.get("slot_assignment_candidate_tz") or state.get("candidate_tz") or DEFAULT_TZ
    assignment_id = state.get("slot_assignment_id")
    action_token = state.get("slot_assignment_action_token")
    if not assignment_id or not action_token:
        await message.answer("Сессия устарела. Запросите новое время через кнопку.")
        return True

    local_dt = _parse_datetime_input(text, candidate_tz)
    window_start_local = None
    window_end_local = None
    requested_start_utc = None
    requested_end_utc = None
    comment = None
    requested_summary = None

    if local_dt is not None:
        requested_start_utc = local_dt.astimezone(timezone.utc)
        requested_summary = local_dt.strftime(TIME_FMT)
    else:
        window_start_local, window_end_local = _parse_manual_availability_window(text, candidate_tz)
        if window_start_local and window_end_local:
            requested_start_utc = window_start_local.astimezone(timezone.utc)
            requested_end_utc = window_end_local.astimezone(timezone.utc)
            requested_summary = _format_manual_window_label(
                window_start_local,
                window_end_local,
                candidate_tz,
            )
        else:
            comment = text or None

    client = BackendClient()
    if not client.configured:
        await message.answer("Сервис временно недоступен.")
        return True

    try:
        status, data = await client.post_json(
            f"/api/slot-assignments/{assignment_id}/request-reschedule",
            {
                "action_token": action_token,
                "candidate_tg_id": candidate_id,
                "requested_start_utc": requested_start_utc.isoformat() if requested_start_utc else None,
                "requested_end_utc": requested_end_utc.isoformat() if requested_end_utc else None,
                "requested_tz": candidate_tz,
                "comment": comment,
            },
        )
    except BackendClientError as exc:
        logger.warning(
            "slot_assignment.request_reschedule.backend_unavailable assignment_id=%s candidate_tg_id=%s error=%s",
            assignment_id,
            candidate_id,
            exc,
        )
        await message.answer("Сервис недоступен. Попробуйте позже.")
        return True

    if status == 404:
        await message.answer("Ссылка устарела. Попросите рекрутёра прислать новое предложение времени.")
        return True
    if status == 409:
        detail = data.get("detail") if isinstance(data, dict) else None
        alternatives = data.get("alternatives") if isinstance(data, dict) else None
        if alternatives and isinstance(alternatives, list):
            items = []
            for raw in alternatives[:5]:
                try:
                    alt_dt = datetime.fromisoformat(str(raw))
                    items.append(alt_dt.astimezone(_safe_zone(candidate_tz)).strftime(TIME_FMT))
                except Exception:
                    continue
            if items:
                await message.answer(
                    "Это время недоступно. Вот ближайшие варианты:\n"
                    + "\n".join(f"• {itm}" for itm in items)
                )
                return True
        await message.answer(detail or "Это время недоступно. Попробуйте выбрать другое.")
        return True
    if status >= 400:
        detail = data.get("detail") if isinstance(data, dict) else None
        await message.answer(detail or "Не удалось отправить запрос. Попробуйте позже.")
        return True

    state_manager = get_state_manager()
    await state_manager.update(
        candidate_id,
        {
            "slot_assignment_state": "reschedule_pending",
            "slot_assignment_id": assignment_id,
            "slot_assignment_action_token": None,
        },
    )

    if requested_summary:
        await message.answer(f"Запрос отправлен рекрутёру: {requested_summary}. Мы сообщим ответ.")
    else:
        await message.answer("Запрос отправлен рекрутёру. Мы передали ваше пожелание и сообщим ответ.")
    return True
