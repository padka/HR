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
    await services.begin_interview(message.from_user.id)


@router.message(Command(commands=["intro", "test2"]))
async def cmd_intro(message: Message) -> None:
    await services.start_introday_flow(message)


@router.callback_query(F.data == "home:start")
async def cb_home_start(callback: CallbackQuery) -> None:
    await services.handle_home_start(callback)


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
    logger.info("noop callback handled", extra={"suffix": suffix or None, "user_id": user_id})

    await callback.answer(message)


@router.message()
async def free_text(message: Message) -> None:
    state = services.get_state_manager().get(message.from_user.id)
    if not state:
        await services.send_welcome(message.from_user.id)
        return
    if state.get("flow") == "interview":
        idx = state.get("t1_idx")
        if isinstance(idx, int):
            await services.handle_test1_answer(message)
