from datetime import datetime, timedelta, timezone
import sys
import types

import pytest

# Provide a tiny aiogram.types stub when the real dependency isn't installed.
try:  # pragma: no cover - best effort import
    import aiogram as _aiogram  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - fallback stub
    fake_aiogram = types.ModuleType("aiogram")
    fake_types = types.ModuleType("aiogram.types")

    class _FakeInlineKeyboardButton:
        def __init__(self, *, text: str, callback_data: str):
            self.text = text
            self.callback_data = callback_data

    class _FakeInlineKeyboardMarkup:
        def __init__(self, *, inline_keyboard):
            self.inline_keyboard = inline_keyboard

    fake_types.InlineKeyboardButton = _FakeInlineKeyboardButton
    fake_types.InlineKeyboardMarkup = _FakeInlineKeyboardMarkup
    fake_aiogram.types = fake_types

    sys.modules["aiogram"] = fake_aiogram
    sys.modules["aiogram.types"] = fake_types

from backend.apps.bot.keyboards import kb_recruiters
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_kb_recruiters_handles_duplicate_names_with_slots():
    async with async_session() as session:
        _first = models.Recruiter(name="Анна", tz="Europe/Moscow", active=True)
        second = models.Recruiter(name="Анна", tz="Europe/Moscow", active=True)
        session.add_all([_first, second])
        await session.flush()

        target_id = second.id
        session.add(
            models.Slot(
                recruiter_id=target_id,
                start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
                status=models.SlotStatus.FREE,
            )
        )
        await session.commit()

    keyboard = await kb_recruiters()

    buttons = [
        btn
        for row in keyboard.inline_keyboard
        for btn in row
        if getattr(btn, "callback_data", "").startswith("pick_rec:")
    ]

    assert buttons, "expected recruiter buttons to be present"
    assert any(btn.callback_data.endswith(str(target_id)) for btn in buttons)
    assert all("Временно нет свободных рекрутёров" not in btn.text for btn in buttons)


@pytest.mark.asyncio
async def test_kb_recruiters_considers_uppercase_slot_statuses():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Алексей", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.flush()

        session.add(
            models.Slot(
                recruiter_id=recruiter.id,
                start_utc=datetime.now(timezone.utc) + timedelta(hours=1),
                status="FREE",
            )
        )
        await session.commit()

    keyboard = await kb_recruiters()

    recruiter_buttons = [
        btn
        for row in keyboard.inline_keyboard
        for btn in row
        if getattr(btn, "callback_data", "").startswith("pick_rec:")
    ]

    assert recruiter_buttons
    assert any(btn.callback_data.endswith(str(recruiter.id)) for btn in recruiter_buttons)
