"""Handlers for Test 1 (mini questionnaire)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import services

router = Router()


@router.callback_query(F.data.startswith("t1opt:"))
async def handle_option(callback: CallbackQuery) -> None:
    await services.handle_test1_option(callback)
