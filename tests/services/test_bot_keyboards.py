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
    fake_client = types.ModuleType("aiogram.client")
    fake_client_bot = types.ModuleType("aiogram.client.bot")
    fake_enums = types.ModuleType("aiogram.enums")

    class _FakeInlineKeyboardButton:
        def __init__(self, *, text: str, callback_data: str):
            self.text = text
            self.callback_data = callback_data

    class _FakeInlineKeyboardMarkup:
        def __init__(self, *, inline_keyboard):
            self.inline_keyboard = inline_keyboard

    class _FakeDefaultBotProperties:
        def __init__(self, **_: object):
            pass

    class _FakeParseMode:
        HTML = "HTML"

    fake_types.InlineKeyboardButton = _FakeInlineKeyboardButton
    fake_types.InlineKeyboardMarkup = _FakeInlineKeyboardMarkup
    fake_client_bot.DefaultBotProperties = _FakeDefaultBotProperties
    fake_enums.ParseMode = _FakeParseMode
    fake_aiogram.types = fake_types
    fake_aiogram.client = fake_client
    fake_client.bot = fake_client_bot

    sys.modules["aiogram"] = fake_aiogram
    sys.modules["aiogram.types"] = fake_types
    sys.modules["aiogram.client"] = fake_client
    sys.modules["aiogram.client.bot"] = fake_client_bot
    sys.modules["aiogram.enums"] = fake_enums

from backend.apps.bot import keyboards
from backend.apps.bot.keyboards import kb_recruiters
from backend.apps.bot.config import DEFAULT_TZ
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
async def test_kb_recruiters_uses_aggregated_repository(monkeypatch):
    class _Obj:
        def __init__(self, rid: int, name: str):
            self.id = rid
            self.name = name

    active_calls = 0

    async def fake_get_active_recruiters():
        nonlocal active_calls
        active_calls += 1
        return [_Obj(1, "Анна"), _Obj(2, "Борис")]

    summary_calls = 0

    async def fake_summary(recruiter_ids, now_utc=None, *, city_id=None):
        nonlocal summary_calls
        summary_calls += 1
        assert set(recruiter_ids) == {1, 2}
        return {1: (datetime.now(timezone.utc), 4)}

    monkeypatch.setattr(keyboards, "get_active_recruiters", fake_get_active_recruiters)
    monkeypatch.setattr(keyboards, "get_recruiters_free_slots_summary", fake_summary)

    keyboard = await keyboards.kb_recruiters()

    assert summary_calls == 1
    assert active_calls == 1
    assert keyboard.inline_keyboard


@pytest.mark.asyncio
async def test_kb_recruiters_handles_uppercase_status():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Борис", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.flush()

        await session.execute(
            models.Slot.__table__.insert().values(
                recruiter_id=recruiter.id,
                start_utc=datetime.now(timezone.utc) + timedelta(hours=1),
                duration_min=60,
                status="FREE",
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
    assert any(btn.callback_data.endswith(str(recruiter.id)) for btn in buttons)


@pytest.mark.asyncio
async def test_kb_recruiters_filters_by_city():
    async with async_session() as session:
        rec1 = models.Recruiter(name="Городской", tz="Europe/Moscow", active=True)
        rec2 = models.Recruiter(name="Дальний", tz="Europe/Samara", active=True)
        city1 = models.City(name="Москва", tz="Europe/Moscow", active=True)
        city2 = models.City(name="Самара", tz="Europe/Samara", active=True)
        rec1.cities.append(city1)
        rec2.cities.append(city2)
        session.add_all([rec1, rec2, city1, city2])
        await session.commit()
        await session.refresh(rec1)
        await session.refresh(rec2)
        await session.refresh(city1)
        await session.refresh(city2)

        now = datetime.now(timezone.utc)
        session.add_all(
            [
                models.Slot(
                    recruiter_id=rec1.id,
                    city_id=city1.id,
                    start_utc=now + timedelta(hours=1),
                    status=models.SlotStatus.FREE,
                ),
                models.Slot(
                    recruiter_id=rec2.id,
                    city_id=city2.id,
                    start_utc=now + timedelta(hours=1),
                    status=models.SlotStatus.FREE,
                ),
            ]
        )
        await session.commit()

    keyboard = await kb_recruiters(candidate_tz=DEFAULT_TZ, city_id=city1.id)
    buttons = [
        btn
        for row in keyboard.inline_keyboard
        for btn in row
        if getattr(btn, "callback_data", "").startswith("pick_rec:")
    ]

    assert buttons
    assert any(btn.callback_data.endswith(str(rec1.id)) for btn in buttons)
    assert all(not btn.callback_data.endswith(str(rec2.id)) for btn in buttons)


@pytest.mark.asyncio
async def test_kb_recruiters_no_slots_has_contact_button():
    async with async_session() as session:
        city = models.City(name="Без слотов", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)

    keyboard = await kb_recruiters(candidate_tz=DEFAULT_TZ, city_id=city.id)

    contact_buttons = [
        btn
        for row in keyboard.inline_keyboard
        for btn in row
        if getattr(btn, "callback_data", "") == "contact:manual"
    ]

    assert contact_buttons, "expected contact button when no recruiters are available"
