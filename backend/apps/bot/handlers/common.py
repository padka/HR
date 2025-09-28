"""Common command handlers and fallbacks."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import services

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await services.begin_interview(message.from_user.id)


@router.message(Command(commands=["intro", "test2"]))
async def cmd_intro(message: Message) -> None:
    await services.start_introday_flow(message)


@router.callback_query(F.data == "home:start")
async def cb_home_start(callback: CallbackQuery) -> None:
    await services.handle_home_start(callback)


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
