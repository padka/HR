"""Handlers for attendance confirmation callbacks."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import services

router = Router()


@router.callback_query(F.data.startswith("att_yes:"))
async def attendance_yes(callback: CallbackQuery) -> None:
    await services.handle_attendance_yes(callback)


@router.callback_query(F.data.startswith("att_no:"))
async def attendance_no(callback: CallbackQuery) -> None:
    await services.handle_attendance_no(callback)
