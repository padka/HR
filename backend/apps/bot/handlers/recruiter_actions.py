"""Handlers for recruiter candidate action callbacks and commands."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import recruiter_service
from ..services import get_recruiter_by_chat_id

router = Router()


@router.callback_query(F.data.startswith("rc:"))
async def recruiter_candidate_action(callback: CallbackQuery) -> None:
    """Route recruiter candidate action callbacks (rc:* prefix)."""
    await recruiter_service.handle_recruiter_callback(callback)


@router.message(Command("inbox"))
async def cmd_inbox(message: Message) -> None:
    """Show incoming candidates waiting for slot assignment."""
    user = message.from_user
    if user is None:
        return

    recruiter = await get_recruiter_by_chat_id(user.id)
    if recruiter is None:
        await message.answer("Неизвестная команда. Введите /start для начала.")
        return

    await recruiter_service.show_recruiter_inbox(user.id, recruiter=recruiter)


@router.message(Command("find"))
async def cmd_find(message: Message) -> None:
    """Search candidates by name or city."""
    user = message.from_user
    if user is None:
        return

    recruiter = await get_recruiter_by_chat_id(user.id)
    if recruiter is None:
        await message.answer("Неизвестная команда. Введите /start для начала.")
        return

    # Extract query from command arguments
    query = (message.text or "").strip()
    # Remove the /find prefix
    if query.startswith("/find"):
        query = query[5:].strip()

    await recruiter_service.search_candidates(user.id, query, recruiter=recruiter)
