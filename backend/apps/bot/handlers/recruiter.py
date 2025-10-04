"""Handlers for recruiter confirmation callbacks."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import services

router = Router()


@router.callback_query(F.data.startswith("approve:"))
async def approve(callback: CallbackQuery) -> None:
    await services.handle_approve_slot(callback)


@router.callback_query(F.data.startswith("reschedule:"))
async def reschedule(callback: CallbackQuery) -> None:
    await services.handle_reschedule_slot(callback)


@router.callback_query(F.data.startswith("reject:"))
async def reject(callback: CallbackQuery) -> None:
    await services.handle_reject_slot(callback)


@router.message(Command("iam"))
async def cmd_iam(message: Message) -> None:
    await services.handle_recruiter_identity_command(message)
