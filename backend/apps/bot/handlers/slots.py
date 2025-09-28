"""Handlers for recruiter and slot selection."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import services

router = Router()


@router.callback_query(F.data.startswith("pick_rec:"))
async def pick_recruiter(callback: CallbackQuery) -> None:
    await services.handle_pick_recruiter(callback)


@router.callback_query(F.data.startswith("refresh_slots:"))
async def refresh_slots(callback: CallbackQuery) -> None:
    await services.handle_refresh_slots(callback)


@router.callback_query(F.data.startswith("pick_slot:"))
async def pick_slot(callback: CallbackQuery) -> None:
    await services.handle_pick_slot(callback)
