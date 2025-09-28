"""Common command handlers and fallbacks."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import services
from ..services import BotContext

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, context: BotContext) -> None:
    await services.begin_interview(context, message.from_user.id)


@router.message(Command(commands=["intro", "test2"]))
async def cmd_intro(message: Message, context: BotContext) -> None:
    await services.start_introday_flow(context, message)


@router.callback_query(F.data == "home:start")
async def cb_home_start(callback: CallbackQuery, context: BotContext) -> None:
    await services.handle_home_start(context, callback)


@router.message()
async def free_text(message: Message, context: BotContext) -> None:
    state = context.state_manager.get(message.from_user.id)
    if not state:
        await services.send_welcome(context, message.from_user.id)
        return
    if state.get("flow") == "interview":
        idx = state.get("t1_idx")
        if isinstance(idx, int):
            await services.handle_test1_answer(context, message)
