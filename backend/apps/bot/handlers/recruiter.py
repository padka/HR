"""Handlers for recruiter confirmation callbacks."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import services

router = Router()


@router.callback_query(F.data.startswith("approve:"))
async def approve(callback: CallbackQuery) -> None:
    await services.handle_approve_slot(callback)


@router.callback_query(F.data.startswith("reject:"))
async def reject(callback: CallbackQuery) -> None:
    await services.handle_reject_slot(callback)
