import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.apps.bot import templates
from backend.apps.bot.services import (
    StateManager,
    configure,
    handle_approve_slot,
)
from backend.apps.bot.state_store import InMemoryStateStore
from backend.core.db import async_session
from backend.domain import models
from backend.domain.models import SlotStatus
from backend.domain.repositories import reject_slot, reserve_slot


class DummyMessage:
    def __init__(self) -> None:
        self.edit_text = AsyncMock()
        self.edit_reply_markup = AsyncMock()
        self.document = None
        self.photo = None
        self.video = None
        self.animation = None


class DummyApproveCallback:
    def __init__(self, cb_id: str, slot_id: int, message: DummyMessage, responses):
        self.id = cb_id
        self.data = f"approve:{slot_id}"
        self.from_user = SimpleNamespace(id=0)
        self.message = message
        self._responses = responses

    async def answer(self, text: str, show_alert: bool = False) -> None:
        self._responses.append((text, show_alert))


class DummyBot:
    def __init__(self) -> None:
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):  # pragma: no cover - helper
        self.messages.append((chat_id, text, kwargs))


@pytest.mark.asyncio
async def test_reapprove_after_reschedule_notifies_new_candidate(monkeypatch):
    templates.clear_cache()

    store = InMemoryStateStore(ttl_seconds=300)
    state_manager = StateManager(store)
    dummy_bot = DummyBot()
    configure(dummy_bot, state_manager)

    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Мария",
            tz="Europe/Moscow",
            active=True,
            tg_chat_id=12345,
        )
        city = models.City(name="Казань", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=6),
            status=SlotStatus.PENDING,
            candidate_tg_id=111,
            candidate_fio="Первый Кандидат",
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    await state_manager.set(
        111,
        {
            "fio": "Первый Кандидат",
            "city_name": "Казань",
            "city_id": city.id,
            "candidate_tz": "Europe/Moscow",
        },
    )

    send_calls = []

    async def fake_send(bot, method, correlation_id):
        send_calls.append((method, correlation_id))
        return SimpleNamespace(message_id=1)

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", fake_send)
    reminder_service = SimpleNamespace(schedule_for_slot=AsyncMock())
    monkeypatch.setattr(
        "backend.apps.bot.services.get_reminder_service",
        lambda: reminder_service,
    )

    responses = []
    approve_cb = DummyApproveCallback("cb-1", slot_id, DummyMessage(), responses)
    await handle_approve_slot(approve_cb)

    assert len(send_calls) == 1, "Первый кандидат должен получить сообщение"

    async with async_session() as session:
        log = await session.scalar(
            select(models.NotificationLog)
            .where(models.NotificationLog.booking_id == slot_id)
            .where(models.NotificationLog.candidate_tg_id == 111)
            .where(models.NotificationLog.type == "candidate_interview_confirmed")
        )
        assert log is not None, "Запись лога должна сохраниться для первого кандидата"

    assert reminder_service.schedule_for_slot.await_count == 1

    await reject_slot(slot_id)

    async with async_session() as session:
        remaining = await session.scalars(
            select(models.NotificationLog).where(
                models.NotificationLog.booking_id == slot_id
            )
        )
        assert not list(remaining), "Логи должны удаляться при освобождении слота"

    await state_manager.set(
        222,
        {
            "fio": "Второй Кандидат",
            "city_name": "Казань",
            "city_id": city.id,
            "candidate_tz": "Europe/Moscow",
        },
    )

    reservation = await reserve_slot(
        slot_id,
        candidate_tg_id=222,
        candidate_fio="Второй Кандидат",
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
    )
    assert reservation.status == "reserved"

    second_cb = DummyApproveCallback("cb-2", slot_id, DummyMessage(), responses)
    await handle_approve_slot(second_cb)

    assert len(send_calls) == 2, "Новый кандидат должен получить уведомление после рескейла"
    assert reminder_service.schedule_for_slot.await_count == 2

    async with async_session() as session:
        log = await session.scalar(
            select(models.NotificationLog)
            .where(models.NotificationLog.booking_id == slot_id)
            .where(models.NotificationLog.candidate_tg_id == 222)
            .where(models.NotificationLog.type == "candidate_interview_confirmed")
        )
        assert log is not None, "Второй кандидат должен иметь собственную запись"

    assert [call.args for call in reminder_service.schedule_for_slot.await_args_list] == [
        (slot_id,),
        (slot_id,),
    ]

    await state_manager.clear()
    await state_manager.close()
