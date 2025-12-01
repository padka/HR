from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.apps.admin_ui.services.slots import ManualSlotError, schedule_manual_candidate_slot
from backend.core.db import async_session
from backend.core.time_utils import ensure_aware_utc
from backend.domain import candidates as candidate_services
from backend.domain import models
from backend.domain.candidates import models as candidate_models
from backend.domain.candidates import status_service
from backend.domain.candidates.status import CandidateStatus
from sqlalchemy import select


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


async def _setup_candidate_recruiter(telegram_id: int, city_tz: str = "Europe/Moscow"):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=telegram_id,
        fio="Тестовый Кандидат",
        city="Москва",
        username=f"candidate_{telegram_id}",
    )

    async with async_session() as session:
        city = models.City(name=f"City {telegram_id}", tz=city_tz, active=True)
        recruiter = models.Recruiter(name=f"Recruiter {telegram_id}", tz=city_tz, active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

    return candidate, city, recruiter


@pytest.mark.asyncio
async def test_schedule_manual_slot_handles_naive_conflicts():
    candidate, city, recruiter = await _setup_candidate_recruiter(telegram_id=101001)

    async with async_session() as session:
        conflict_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime(2024, 7, 1, 10, 0),  # intentionally naive
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        session.add(conflict_slot)
        await session.commit()

    dt_utc = datetime(2024, 7, 1, 9, 30, tzinfo=timezone.utc)

    with pytest.raises(ManualSlotError) as excinfo:
        await schedule_manual_candidate_slot(
            candidate=candidate,
            recruiter=recruiter,
            city=city,
            dt_utc=dt_utc,
            slot_tz=city.tz,
        )

    assert "Конфликт расписания" in str(excinfo.value)


@pytest.mark.asyncio
async def test_schedule_manual_slot_normalizes_naive_input():
    candidate, city, recruiter = await _setup_candidate_recruiter(telegram_id=101002)

    async with async_session() as session:
        conflict_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime(2024, 7, 2, 12, 45, tzinfo=timezone.utc),
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        session.add(conflict_slot)
        await session.commit()

    dt_utc = datetime(2024, 7, 2, 12, 30)  # naive input

    with pytest.raises(ManualSlotError) as excinfo:
        await schedule_manual_candidate_slot(
            candidate=candidate,
            recruiter=recruiter,
            city=city,
            dt_utc=dt_utc,
            slot_tz=city.tz,
        )

    assert "Конфликт расписания" in str(excinfo.value)


@pytest.mark.asyncio
async def test_schedule_manual_slot_creates_entry_without_conflicts(monkeypatch):
    candidate, city, recruiter = await _setup_candidate_recruiter(telegram_id=101003)

    async def fake_reserve_slot(*_args, **_kwargs):
        return SimpleNamespace(status="reserved", slot=None)

    async def fake_approve_slot_and_notify(slot_id: int, *, force_notify: bool = False):
        return SimpleNamespace(status="approved", slot=SimpleNamespace(id=slot_id), message="ok")

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.slots.reserve_slot",
        fake_reserve_slot,
    )
    monkeypatch.setattr(
        "backend.apps.admin_ui.services.slots.approve_slot_and_notify",
        fake_approve_slot_and_notify,
    )

    dt_utc = datetime(2024, 7, 3, 10, 0, tzinfo=timezone.utc)
    result = await schedule_manual_candidate_slot(
        candidate=candidate,
        recruiter=recruiter,
        city=city,
        dt_utc=dt_utc,
        slot_tz=city.tz,
    )

    assert result.status == "approved"

    async with async_session() as session:
        stored_slot = await session.scalar(
            select(models.Slot).where(models.Slot.recruiter_id == recruiter.id)
        )
        assert stored_slot is not None
        assert ensure_aware_utc(stored_slot.start_utc) == ensure_aware_utc(dt_utc)
