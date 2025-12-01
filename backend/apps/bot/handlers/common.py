"""Common command handlers and fallbacks."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import services

router = Router()

logger = logging.getLogger(__name__)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if user is None:
        logger.warning("/start command without user", extra={"has_user": False})
        return

    user_id = getattr(user, "id", None)
    if user_id is None:
        logger.warning("/start command without user", extra={"has_user": True})
        return

    username = getattr(user, "username", None)
    logger.info(
        "User started interview",
        extra={
            "user_id": user_id,
            "username": username,
            "first_name": getattr(user, "first_name", None),
            "last_name": getattr(user, "last_name", None),
        }
    )
    await services.begin_interview(user_id, username=username)


@router.message(Command(commands=["intro", "test2"]))
async def cmd_intro(message: Message) -> None:
    await services.start_introday_flow(message)


@router.callback_query(F.data == "home:start")
async def cb_home_start(callback: CallbackQuery) -> None:
    await services.handle_home_start(callback)


@router.callback_query(F.data == "contact:manual")
async def cb_contact_manual(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user:
        await callback.answer()
        return

    sent = await services.send_manual_scheduling_prompt(user.id)
    if sent:
        await callback.answer("Откройте чат с рекрутёром по кнопке ниже")
    else:
        await callback.answer("Ссылка на рекрутёра уже отправлена выше")


@router.callback_query(F.data.startswith("noop:"))
async def cb_noop_hint(callback: CallbackQuery) -> None:
    hints = {
        "no_recruiters": "Сейчас нет активных рекрутёров",
        "no_slots": "Свободные слоты появятся позже",
    }

    suffix = ""
    if callback.data:
        _, _, suffix = callback.data.partition(":")

    message = hints.get(suffix, "Нет доступной информации")

    user_id = callback.from_user.id if callback.from_user else "unknown"
    logger.info(
        "noop callback handled", extra={"suffix": suffix or None, "user_id": user_id}
    )

    await callback.answer(message)


@router.message()
async def free_text(message: Message) -> None:
    user = message.from_user
    if user is None:
        logger.warning("free text received without user", extra={"has_user": False})
        return

    user_id = getattr(user, "id", None)
    if user_id is None:
        logger.warning("free text received without user", extra={"has_user": True})
        return

    state_manager = services.get_state_manager()

    try:
        state = await state_manager.get(user_id)
    except Exception:  # pragma: no cover - defensive guard
        logger.exception(
            "failed to load state for free text", extra={"user_id": user_id}
        )
        return

    if not state:
        return

    if not isinstance(state, dict):
        logger.warning(
            "unexpected state payload",
            extra={"user_id": user_id, "type": type(state).__name__},
        )
        return

    # Capture причины отказа от ознакомительного дня, если ждём ответ
    if state.get("awaiting_intro_decline_reason"):
        handled = await services.capture_intro_decline_reason(message, state)
        if handled:
            return

    if state.get("manual_availability_expected"):
        payload_text = (message.text or message.caption or "").strip()
        if not payload_text:
            await message.answer("Напишите, пожалуйста, удобный диапазон в формате «25.07 12:00-16:00».")
            return
        handled = await services.record_manual_availability_response(user_id, payload_text)
        if handled:
            return

    if state.get("flow") != "interview":
        return

    idx = state.get("t1_idx")
    if not isinstance(idx, int):
        idx = state.get("t1_current_idx")
    if isinstance(idx, int):
        await services.handle_test1_answer(message)
