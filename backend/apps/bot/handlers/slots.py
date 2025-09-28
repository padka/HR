"""Handlers for recruiter and slot selection."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import services
from ..services import BotContext

router = Router()


@router.callback_query(F.data.startswith("pick_rec:"))
async def pick_recruiter(callback: CallbackQuery, context: BotContext) -> None:
    await services.handle_pick_recruiter(context, callback)


@router.callback_query(F.data.startswith("refresh_slots:"))
async def refresh_slots(callback: CallbackQuery, context: BotContext) -> None:
    await services.handle_refresh_slots(context, callback)


@router.callback_query(F.data.startswith("pick_slot:"))
async def pick_slot(callback: CallbackQuery, context: BotContext) -> None:
    await services.handle_pick_slot(context, callback)
