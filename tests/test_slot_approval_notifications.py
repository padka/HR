from datetime import datetime, timedelta, timezone

import pytest

from backend.apps.bot import services as bot_services
from backend.core.db import async_session
from backend.domain import candidates as candidate_services
from backend.domain import models
from backend.domain.models import SlotStatus


@pytest.mark.asyncio
async def test_force_notify_resends_for_booked_slot(monkeypatch):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=8800555,
        fio="Test Candidate",
        city="Москва",
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Тестовый рекрутёр", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
            status=SlotStatus.BOOKED,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

    send_calls = []

    async def fake_send(bot, method, correlation_id):
        send_calls.append((method.chat_id, method.text, correlation_id))

    class DummyReminder:
        async def schedule_for_slot(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", fake_send)
    monkeypatch.setattr("backend.apps.bot.services.get_bot", lambda: object())
    monkeypatch.setattr("backend.apps.bot.services.get_reminder_service", lambda: DummyReminder())

    result = await bot_services.approve_slot_and_notify(slot.id)
    assert result.status == "already"
    assert not send_calls

    result_force = await bot_services.approve_slot_and_notify(slot.id, force_notify=True)
    assert result_force.status == "approved"
    assert len(send_calls) == 1
