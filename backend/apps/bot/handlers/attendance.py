"""Handlers for attendance confirmation callbacks."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import services
from ..services import BotContext

router = Router()


@router.callback_query(F.data.startswith("att_yes:"))
async def attendance_yes(callback: CallbackQuery, context: BotContext) -> None:
    await services.handle_attendance_yes(context, callback)


@router.callback_query(F.data.startswith("att_no:"))
async def attendance_no(callback: CallbackQuery, context: BotContext) -> None:
    await services.handle_attendance_no(context, callback)
