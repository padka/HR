"""Handlers for slot assignment offer callbacks."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import slot_assignment_flow

router = Router()


@router.callback_query(F.data.startswith("{"))
async def handle_slot_assignment_callback(callback: CallbackQuery) -> None:
    handled = await slot_assignment_flow.handle_slot_assignment_callback(callback)
    if not handled:
        await callback.answer()
