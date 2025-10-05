from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.apps.bot import templates
from backend.apps.bot.config import TEST1_QUESTIONS
from backend.apps.bot.services import StateManager, configure as configure_bot_services, finalize_test1
from backend.apps.bot.state_store import InMemoryStateStore
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import TestResult, User


class DummyBot:
    def __init__(self):
        self.messages = []
        self.documents = []

    async def send_message(self, chat_id, text, **_kwargs):
        self.messages.append((chat_id, text))

    async def send_document(self, chat_id, document, caption=None, **_kwargs):
        self.documents.append((chat_id, document, caption))


@pytest.mark.asyncio
async def test_finalize_test1_notifies_recruiter():
    templates.clear_cache()

    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Notifier",
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=9999,
        )
        city = models.City(name="Казань", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()

    store = InMemoryStateStore(ttl_seconds=60)
    state_manager = StateManager(store)
    user_id = 4242
    await state_manager.set(
        user_id,
        {
            "fio": "Test User",
            "city_name": "Казань",
            "city_id": city.id,
            "candidate_tz": "Europe/Moscow",
            "test1_answers": {TEST1_QUESTIONS[0]["id"]: "Answer"},
        },
    )

    bot = DummyBot()
    configure_bot_services(bot, state_manager)

    await finalize_test1(user_id)

    assert bot.documents, "Recruiter should receive Test 1 document"
    doc_entry = bot.documents[0]
    assert doc_entry[0] == recruiter.tg_chat_id
    file_obj = doc_entry[1]
    file_path = getattr(file_obj, "path", str(file_obj))
    assert "test1_Test User" in str(file_path)

    updated_state = await state_manager.get(user_id)
    assert updated_state.get("t1_notified") is True

    async with async_session() as session:
        db_user = await session.scalar(select(User).where(User.telegram_id == user_id))
        assert db_user is not None
        assert db_user.fio == "Test User"
        result = await session.scalar(select(TestResult).where(TestResult.user_id == db_user.id))
        assert result is not None


@pytest.mark.asyncio
async def test_finalize_test1_deduplicates_by_chat_id():
    templates.clear_cache()

    async with async_session() as session:
        shared_chat = 5555
        recruiter = models.Recruiter(
            name="Ответственный",
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=shared_chat,
        )
        backup = models.Recruiter(
            name="Бэкап",
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=shared_chat,
        )
        city = models.City(name="Уфа", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, backup, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(backup)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()

        session.add(
            models.Slot(
                recruiter_id=backup.id,
                city_id=city.id,
                start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
                status=models.SlotStatus.FREE,
            )
        )
        await session.commit()

    store = InMemoryStateStore(ttl_seconds=60)
    state_manager = StateManager(store)
    user_id = 7373
    await state_manager.set(
        user_id,
        {
            "fio": "Дубликат",
            "city_name": "Уфа",
            "city_id": city.id,
            "candidate_tz": "Europe/Moscow",
            "test1_answers": {TEST1_QUESTIONS[0]["id"]: "Answer"},
        },
    )

    bot = DummyBot()
    configure_bot_services(bot, state_manager)

    await finalize_test1(user_id)

    assert len(bot.documents) == 1, "expected single notification per chat"
    chat_id, *_ = bot.documents[0]
    assert chat_id == shared_chat
