from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete

from backend.apps.bot import templates
from backend.apps.bot.services import (
    StateManager,
    configure as configure_bot_services,
    fmt_dt_local,
    handle_attendance_yes,
)
from backend.apps.bot.state_store import InMemoryStateStore
from backend.core.db import async_session
from backend.domain import models
import backend.apps.bot.services as bot_services


class DummyMessage:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.reply_markup_removed = False

    async def edit_text(self, text: str, **_kwargs) -> None:
        self.texts.append(text)

    async def edit_caption(self, caption: str, **_kwargs) -> None:
        self.texts.append(caption)

    async def edit_reply_markup(self, reply_markup=None, **_kwargs) -> None:
        self.reply_markup_removed = reply_markup is None

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
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = DummyMessage()
        self.answers: list[str] = []
        self.from_user = SimpleNamespace(id=0)

    async def answer(self, text: str = "", **_kwargs) -> None:
        self.answers.append(text)


class DummyBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **_kwargs) -> None:
        self.messages.append((chat_id, text))


async def _prepare_slot() -> tuple[models.Recruiter, models.City, models.Slot]:
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Attendee",
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=5555,
            telemost_url="https://telemost.yandex.ru/j/custom",
        )
        city = models.City(name="Attendance City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            start_utc=now + timedelta(hours=5),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=777,
            candidate_fio="Candidate User",
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
    return recruiter, city, slot


@pytest.mark.asyncio
async def test_attendance_confirmation_uses_templates_and_notifies_recruiter():
    recruiter, city, slot = await _prepare_slot()

    async with async_session() as session:
        await session.execute(
            delete(models.Template).where(
                models.Template.key.in_(
                    [
                        "att_confirmed_link",
                        "att_confirmed_ack",
                        "att_confirmed_recruiter",
                    ]
                )
            )
        )
        session.add_all(
            [
                models.Template(
                    city_id=None,
                    key="att_confirmed_link",
                    content="Глобальный линк: {link} — {dt}",
                ),
                models.Template(
                    city_id=None,
                    key="att_confirmed_ack",
                    content="Спасибо, участие подтверждено!",
                ),
                models.Template(
                    city_id=None,
                    key="att_confirmed_recruiter",
                    content="Кандидат {candidate} подтвердил встречу {dt}",
                ),
            ]
        )
        await session.commit()

    templates.clear_cache()

    store = InMemoryStateStore(ttl_seconds=60)
    state_manager = StateManager(store)
    bot = DummyBot()

    original_bot = bot_services._bot
    original_state = bot_services._state_manager
    configure_bot_services(bot, state_manager)

    try:
        cb = DummyCallback(f"att_yes:{slot.id}")
        await handle_attendance_yes(cb)

        assert cb.answers[-1] == "Подтверждено"
        assert cb.message.reply_markup_removed is True
        assert cb.message.texts == ["Спасибо, участие подтверждено!"]

        assert len(bot.messages) == 2
        candidate_msg = bot.messages[0]
        recruiter_msg = bot.messages[1]

        expected_dt = fmt_dt_local(slot.start_utc, slot.candidate_tz or "Europe/Moscow")
        assert candidate_msg == (
            slot.candidate_tg_id,
            f"Глобальный линк: {recruiter.telemost_url} — {expected_dt}",
        )
        assert recruiter_msg == (
            recruiter.tg_chat_id,
            f"Кандидат {slot.candidate_fio} подтвердил встречу {fmt_dt_local(slot.start_utc, recruiter.tz)}",
        )

        async with async_session() as session:
            fresh = await session.get(models.Slot, slot.id)
            assert fresh is not None
            assert fresh.attendance_confirmed_at is not None

        # Second confirmation should not spam messages
        cb_repeat = DummyCallback(f"att_yes:{slot.id}")
        await handle_attendance_yes(cb_repeat)
        assert cb_repeat.answers[-1] == "Уже подтверждено ✔️"
        assert len(bot.messages) == 2
    finally:
        bot_services._bot = original_bot
        bot_services._state_manager = original_state
        templates.clear_cache()
