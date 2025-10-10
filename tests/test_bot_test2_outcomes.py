from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.apps.bot import templates
from backend.apps.bot.config import TEST2_QUESTIONS
from backend.apps.bot.services import (
    StateManager,
    configure as configure_bot_services,
    finalize_test2,
)
from backend.apps.bot.state_store import InMemoryStateStore
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import (
    CandidateTestOutcome,
    CandidateTestOutcomeDelivery,
    User,
)


class DummyBot:
    def __init__(self):
        self.messages = []
        self.documents = []

    async def send_message(self, chat_id, text, **_kwargs):
        self.messages.append((chat_id, text))

    async def send_document(self, chat_id, document, caption=None, **_kwargs):
        self.documents.append((chat_id, document, caption))
        return type("Sent", (), {"message_id": len(self.documents)})()


@pytest.mark.asyncio
async def test_finalize_test2_persists_outcome_and_deduplicates():
    templates.clear_cache()

    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Тестовый", tz="Europe/Moscow", active=True, tg_chat_id=8080
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
    user_id = 5252

    attempts = {}
    now = datetime.now()
    for idx, question in enumerate(TEST2_QUESTIONS):
        attempts[idx] = {
            "answers": [
                {
                    "answer": question.get("correct", 0),
                    "time": now.isoformat(),
                    "overtime": False,
                }
            ],
            "is_correct": True,
            "start_time": now - timedelta(seconds=5),
        }

    await state_manager.set(
        user_id,
        {
            "fio": "Финалист",
            "city_name": "Казань",
            "city_id": city.id,
            "candidate_tz": "Europe/Moscow",
            "t2_attempts": attempts,
            "flow": "intro",
        },
    )

    bot = DummyBot()
    configure_bot_services(bot, state_manager)

    await finalize_test2(user_id)

    # outcome is shared with recruiter exactly once
    assert bot.documents, "Recruiter should receive Test 2 outcome"
    chat_id, file_obj, caption = bot.documents[0]
    assert chat_id == recruiter.tg_chat_id
    file_path = getattr(file_obj, "path", None)
    assert file_path is not None

    async with async_session() as session:
        db_user = await session.scalar(select(User).where(User.telegram_id == user_id))
        assert db_user is not None
        outcomes = (
            await session.execute(
                select(CandidateTestOutcome).where(
                    CandidateTestOutcome.user_id == db_user.id
                )
            )
        ).scalars().all()
        assert len(outcomes) == 1
        outcome = outcomes[0]
        assert outcome.status == "passed"

        deliveries = (
            await session.execute(
                select(CandidateTestOutcomeDelivery).where(
                    CandidateTestOutcomeDelivery.outcome_id == outcome.id
                )
            )
        ).scalars().all()
        assert deliveries and deliveries[0].chat_id == recruiter.tg_chat_id

    # Duplicate completion should not resend file
    await finalize_test2(user_id)
    assert len(bot.documents) == 1
