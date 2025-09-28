"""Handlers for Test 2 multiple choice flow."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import services
from ..services import BotContext

router = Router()


@router.callback_query(F.data.startswith("answer_"))
async def handle_test2(callback: CallbackQuery, context: BotContext) -> None:
    await services.handle_test2_answer(context, callback)
