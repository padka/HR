"""Handlers for interview lifecycle events."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .. import services
from ..events import InterviewSuccessEvent
from backend.domain.repositories import add_bot_message_log


router = Router()

logger = logging.getLogger(__name__)


@services.register_interview_success_handler
async def on_interview_success(event: InterviewSuccessEvent) -> None:
    bot = services.get_bot()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пройти Тест 2", callback_data="test2:start")]]
    )

    message_text = "Поздравляем! Вы успешно прошли собеседование 🎉"
    payload = {
        "city_id": event.city_id,
        "city_name": event.city_name,
        "candidate_name": event.candidate_name,
        "required": event.required,
    }

    sent_message = None
    try:
        sent_message = await bot.send_message(
            event.candidate_id,
            message_text,
            reply_markup=keyboard,
        )

        # Update candidate status to TEST2_SENT after successful message delivery
        try:
            from backend.domain.candidates.status_service import set_status_test2_sent
            await set_status_test2_sent(event.candidate_id)
        except Exception:
            logger.exception("Failed to update candidate status to TEST2_SENT for candidate %s", event.candidate_id)

    except TelegramBadRequest as exc:
        payload["status"] = "bad_request"
        payload["error"] = str(exc)
        logger.warning(
            "Failed to deliver Test 2 invite",
            extra={"candidate_id": event.candidate_id},
            exc_info=True,
        )
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        payload["status"] = "failed"
        payload["error"] = str(exc)
        logger.exception(
            "Unexpected error while sending Test 2 invite",
            extra={"candidate_id": event.candidate_id},
        )
        raise
    else:
        payload["status"] = "sent"
        message_id = getattr(sent_message, "message_id", None)
        if message_id is not None:
            payload["message_id"] = int(message_id)
    finally:
        try:
            payload.setdefault("status", "unknown")
            await add_bot_message_log(
                "test2_invite",
                candidate_tg_id=event.candidate_id,
                slot_id=event.slot_id,
                payload=payload,
            )
        except Exception:  # pragma: no cover - log persistence guard
            logger.exception(
                "Failed to write bot message log for Test 2 invite",
                extra={"candidate_id": event.candidate_id},
            )


@router.callback_query(F.data == "test2:start")
async def start_test2_callback(callback: CallbackQuery) -> None:
    user = callback.from_user
    if user is None:
        await callback.answer()
        return

    try:
        await services.launch_test2(user.id)
        try:
            if callback.message:
                await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass
        await callback.answer("Тест 2 запускается")
    except Exception:  # pragma: no cover - defensive alert
        await callback.answer("Не удалось запустить Тест 2", show_alert=True)
