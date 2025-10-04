from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.apps.bot import templates
from backend.apps.bot.services import (
    StateManager,
    configure as configure_bot_services,
    handle_reschedule_slot,
    handle_reject_slot,
)
from backend.apps.bot.state_store import InMemoryStateStore
from backend.core.db import async_session
from backend.domain import models


class DummyMessage:
    def __init__(self):
        self.texts = []
        self.reply_markup_removed = False

    async def edit_text(self, text, **_kwargs):
        self.texts.append(text)

    async def edit_reply_markup(self, reply_markup=None):
        self.reply_markup_removed = reply_markup is None

    async def edit_caption(self, caption, **_kwargs):
        self.texts.append(caption)

    @property
    def document(self):
        return None

    @property
    def photo(self):
        return None

    @property
    def video(self):
        return None

    @property
    def animation(self):
        return None


class DummyCallback:
    def __init__(self, data: str, user_id: int):
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = DummyMessage()
        self.answers = []

    async def answer(self, text: str = "", **_kwargs):
        self.answers.append(text)


class DummyBot:
    def __init__(self):
        self.messages = []
        self.documents = []

    async def send_message(self, chat_id, text, **_kwargs):
        self.messages.append((chat_id, text))

    async def send_document(self, chat_id, document, caption=None, **_kwargs):
        self.documents.append((chat_id, document, caption))


async def _prepare_slot(status=models.SlotStatus.PENDING):
    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Tester", tz="Europe/Moscow", active=True, tg_chat_id=5555
        )
        city = models.City(name="Test City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
            status=status,
            candidate_tg_id=777,
            candidate_fio="Candidate",
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
    return recruiter, city, slot


@pytest.mark.asyncio
async def test_reschedule_slot_sends_notice(monkeypatch):
    recruiter, city, slot = await _prepare_slot()
    templates.clear_cache()

    store = InMemoryStateStore(ttl_seconds=60)
    state_manager = StateManager(store)
    await state_manager.set(
        slot.candidate_tg_id,
        {
            "fio": "Candidate",
            "city_name": city.name,
            "city_id": city.id,
            "candidate_tz": "Europe/Moscow",
            "picked_slot_id": slot.id,
            "picked_recruiter_id": recruiter.id,
        },
    )

    bot = DummyBot()
    configure_bot_services(bot, state_manager)

    cb = DummyCallback(f"reschedule:{slot.id}", recruiter.tg_chat_id)
    await handle_reschedule_slot(cb)

    assert len(bot.messages) == 1
    message_text = bot.messages[0][1]
    assert "Перенести" in message_text or "Выбор рекрутёра" in message_text
    assert "Выбор рекрутёра" in message_text

    async with async_session() as session:
        fresh = await session.get(models.Slot, slot.id)
        assert fresh is not None
        assert fresh.status == models.SlotStatus.FREE
        assert fresh.candidate_tg_id is None

    updated_state = await state_manager.get(slot.candidate_tg_id)
    assert updated_state is not None
    assert updated_state.get("picked_slot_id") is None


@pytest.mark.asyncio
async def test_reject_slot_sends_rejection(monkeypatch):
    recruiter, city, slot = await _prepare_slot()
    templates.clear_cache()

    store = InMemoryStateStore(ttl_seconds=60)
    state_manager = StateManager(store)
    await state_manager.set(
        slot.candidate_tg_id,
        {
            "fio": "Candidate",
            "city_name": city.name,
            "city_id": city.id,
            "candidate_tz": "Europe/Moscow",
        },
    )

    bot = DummyBot()
    configure_bot_services(bot, state_manager)

    cb = DummyCallback(f"reject:{slot.id}", recruiter.tg_chat_id)
    await handle_reject_slot(cb)

    assert len(bot.messages) == 1
    rejection_text = bot.messages[0][1]
    assert "Спасибо за время" in rejection_text

    async with async_session() as session:
        fresh = await session.get(models.Slot, slot.id)
        assert fresh is not None
        assert fresh.status == models.SlotStatus.FREE
        assert fresh.candidate_tg_id is None

    updated_state = await state_manager.get(slot.candidate_tg_id)
    assert updated_state is not None
    assert updated_state.get("flow") == "rejected"

