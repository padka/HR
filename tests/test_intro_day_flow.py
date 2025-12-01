from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.apps.bot.services import capture_intro_decline_reason, configure
from backend.apps.bot.state_store import InMemoryStateStore, StateManager
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.models import Recruiter, Slot, SlotStatus


class DummyBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append({"chat_id": chat_id, "text": text, **kwargs})


class DummyMessage:
    def __init__(self, text: str, user_id: int):
        self.text = text
        self.caption = None
        self.from_user = SimpleNamespace(id=user_id)
        self.answers = []

    async def answer(self, text: str):
        self.answers.append(text)


@pytest.mark.asyncio
async def test_intro_day_decline_reason_saved_and_sent():
    user_id = 2222001
    now = datetime.now(timezone.utc) + timedelta(days=1)

    async with async_session() as session:
        user = User(telegram_id=user_id, fio="Intro User", city="Test", is_active=True)
        session.add(user)
        recruiter = Recruiter(name="Intro Rec", tg_chat_id=999000, tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.flush()
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            candidate_city_id=None,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=now,
            duration_min=60,
            status=SlotStatus.CONFIRMED_BY_CANDIDATE,
            candidate_tg_id=user_id,
            candidate_fio="Intro User",
        )
        session.add(slot)
        await session.commit()

    bot = DummyBot()
    state_manager = StateManager(InMemoryStateStore(ttl_seconds=30))
    configure(bot, state_manager, dispatcher=None)

    state = {"awaiting_intro_decline_reason": {"slot_id": slot.id, "candidate_fio": "Intro User"}}
    await state_manager.set(user_id, state)

    message = DummyMessage("Не смогу", user_id)
    handled = await capture_intro_decline_reason(message, state)
    assert handled is True

    async with async_session() as session:
        updated_user = await session.scalar(select(User).where(User.telegram_id == user_id))
    assert updated_user.intro_decline_reason == "Не смогу"

    # Recruiter should receive forwarded reason
    assert bot.sent_messages
    assert bot.sent_messages[-1]["chat_id"] == 999000
    assert "Не смогу" in bot.sent_messages[-1]["text"]
