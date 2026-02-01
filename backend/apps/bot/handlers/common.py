"""Common command handlers and fallbacks."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import services
from .. import slot_assignment_flow
from ..services import show_recruiter_dashboard
from backend.domain import analytics
from backend.domain.candidates import bind_telegram_to_candidate, get_user_by_telegram_id

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
    try:
        candidate = await get_user_by_telegram_id(user_id)
        await analytics.log_funnel_event(
            analytics.FunnelEvent.BOT_START,
            user_id=user_id,
            candidate_id=candidate.id if candidate else None,
            metadata={"channel": "telegram"},
        )
    except Exception:
        logger.exception("Failed to log BOT_START event", extra={"user_id": user_id})
    try:
        await services.begin_interview(user_id, username=username)
    except Exception:
        logger.exception(
            "begin_interview failed for user %s", user_id,
            extra={"user_id": user_id, "username": username},
        )
        try:
            await message.answer(
                "Произошла ошибка при запуске. Попробуйте /start ещё раз."
            )
        except Exception:
            pass


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    """Show recruiter dashboard if chat belongs to recruiter.

    Non-recruiter users receive a generic "unknown command" reply to avoid
    leaking the existence of staff-only functionality.
    """
    user = message.from_user
    if user is None:
        return

    from backend.apps.bot.services import get_recruiter_by_chat_id

    recruiter = await get_recruiter_by_chat_id(user.id)
    if recruiter is None:
        logger.info("Unauthorized /admin attempt", extra={"user_id": user.id})
        await message.answer("Неизвестная команда. Введите /start для начала.")
        return

    await show_recruiter_dashboard(user.id, recruiter=recruiter)


@router.message(Command("invite"))
async def cmd_invite(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    user_id = getattr(user, "id", None)
    if user_id is None:
        return
    parts = (message.text or "").split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ""
    if not token:
        await message.answer("Отправьте /invite <токен>, чтобы привязать Telegram к анкете.")
        return
    bound = await bind_telegram_to_candidate(
        token=token,
        telegram_id=user_id,
        username=getattr(user, "username", None),
    )
    if bound:
        await message.answer("✅ Telegram привязан. Введите /start для продолжения.")
    else:
        await message.answer("❌ Токен не найден или уже использован.")


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

    if state.get("slot_assignment_state") == slot_assignment_flow.STATE_WAITING_DATETIME:
        handled = await slot_assignment_flow.handle_datetime_input(message, state)
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
