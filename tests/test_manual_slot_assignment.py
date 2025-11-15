from datetime import datetime, timedelta, timezone

import pytest

from backend.apps.admin_ui.services.slots import ManualSlotError, schedule_manual_candidate_slot
from backend.core.db import async_session
from backend.domain import candidates as candidate_services
from backend.domain import models
from backend.domain.candidates import models as candidate_models
from backend.domain.candidates import status_service
from backend.domain.candidates.status import CandidateStatus


@pytest.mark.asyncio
async def test_manual_slot_scheduling_flow(monkeypatch):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=99001,
        fio="Алексей Тестовый",
        city="Москва",
        username="test_candidate",
    )

    async with async_session() as session:
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Марина Рекрутер", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

    async def fake_send_with_retry(bot, method, correlation_id):
        return None

    class DummyReminder:
        async def schedule_for_slot(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", fake_send_with_retry)
    monkeypatch.setattr("backend.apps.bot.services.get_bot", lambda: object())
    monkeypatch.setattr("backend.apps.bot.services.get_reminder_service", lambda: DummyReminder())

    await status_service.set_status_test1_completed(candidate.telegram_id)

    dt_utc = datetime.now(timezone.utc) + timedelta(days=1)
    result = await schedule_manual_candidate_slot(
        candidate=candidate,
        recruiter=recruiter,
        city=city,
        dt_utc=dt_utc,
        slot_tz=city.tz,
    )

    assert result.status in {"approved", "notify_failed"}
    assert result.slot is not None

    async with async_session() as session:
        refreshed = await session.get(candidate_models.User, candidate.id)
        assert refreshed.candidate_status == CandidateStatus.INTERVIEW_SCHEDULED

    with pytest.raises(ManualSlotError):
        await schedule_manual_candidate_slot(
            candidate=candidate,
            recruiter=recruiter,
            city=city,
            dt_utc=dt_utc + timedelta(hours=1),
            slot_tz=city.tz,
        )
