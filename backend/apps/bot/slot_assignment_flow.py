"""Slot assignment dialog handlers for candidate callbacks and datetime input."""

from __future__ import annotations

import json
import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from backend.apps.bot.backend_client import BackendClient, BackendClientError
from backend.apps.bot.config import DEFAULT_TZ, TIME_FMT
from backend.apps.bot.services import get_bot, get_state_manager

STATE_WAITING_DATETIME = "waiting_candidate_datetime_input"

WORKDAY_START = time(9, 0)
WORKDAY_END = time(20, 0)
MAX_DAYS_AHEAD = 60
MINUTE_STEP = 15


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
    except BackendClientError:
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
    bot = get_bot()
    message_text = data.get("message") if isinstance(data, dict) else None
    await bot.send_message(candidate_id, message_text or "✅ Спасибо! Время подтверждено.")


async def _handle_reschedule_prompt(
    callback: CallbackQuery,
    assignment_id: int,
    action_token: str,
    candidate_id: int,
) -> None:
    state_manager = get_state_manager()
    await state_manager.update(
        candidate_id,
        {
            "slot_assignment_state": STATE_WAITING_DATETIME,
            "slot_assignment_id": assignment_id,
            "slot_assignment_action_token": action_token,
        },
    )
    await callback.answer()
    bot = get_bot()
    await bot.send_message(
        candidate_id,
        "Введите желаемые дату и время в формате «дд.мм чч:мм».\n"
        f"Например: {datetime.now().strftime(TIME_FMT)}",
    )


async def _handle_decline(
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
            f"/api/slot-assignments/{assignment_id}/decline",
            {
                "action_token": action_token,
                "candidate_tg_id": candidate_id,
            },
        )
    except BackendClientError:
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
    await bot.send_message(candidate_id, message_text or "Мы зафиксировали отказ. Спасибо за ответ.")


def _parse_datetime_input(text: str, tz_name: Optional[str]) -> Optional[datetime]:
    value = (text or "").strip()
    if not value:
        return None
    match = re.search(r"(\d{1,2}\.\d{1,2})\s+(\d{1,2}:\d{2})", value)
    if not match:
        return None

    raw = f"{match.group(1)} {match.group(2)}"
    try:
        naive = datetime.strptime(raw, TIME_FMT)
    except ValueError:
        return None

    zone = _safe_zone(tz_name)
    now_local = datetime.now(zone)
    candidate_dt = naive.replace(year=now_local.year, tzinfo=zone)
    if candidate_dt < now_local:
        return None
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

    local_dt = _parse_datetime_input(text, candidate_tz)
    if local_dt is None:
        await message.answer("Не удалось распознать дату. Формат: «дд.мм чч:мм».")
        return True

    if local_dt.time() < WORKDAY_START or local_dt.time() > WORKDAY_END:
        await message.answer("Введите время в рабочем диапазоне 09:00–20:00.")
        return True

    if local_dt.minute % MINUTE_STEP != 0:
        await message.answer("Пожалуйста, укажите время с шагом 15 минут.")
        return True

    if local_dt > datetime.now(_safe_zone(candidate_tz)) + timedelta(days=MAX_DAYS_AHEAD):
        await message.answer("Дата слишком далеко. Укажите время в пределах 60 дней.")
        return True

    requested_utc = local_dt.astimezone(timezone.utc)
    assignment_id = state.get("slot_assignment_id")
    action_token = state.get("slot_assignment_action_token")
    if not assignment_id or not action_token:
        await message.answer("Сессия устарела. Запросите новое время через кнопку.")
        return True

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
                "requested_start_utc": requested_utc.isoformat(),
                "requested_tz": candidate_tz,
                "comment": None,
            },
        )
    except BackendClientError:
        await message.answer("Сервис недоступен. Попробуйте позже.")
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

    await message.answer("Запрос отправлен рекрутёру. Мы сообщим ответ.")
    return True
