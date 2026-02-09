from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.apps.admin_ui.services.slots import (
    ManualSlotError,
    schedule_manual_candidate_slot,
)
from backend.core.db import async_session
from backend.core.time_utils import ensure_aware_utc
from backend.domain import candidates as candidate_services, models
from backend.domain.candidates import models as candidate_models, status_service
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
        recruiter = models.Recruiter(
            name="Марина Рекрутер", tz="Europe/Moscow", active=True
        )
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

    monkeypatch.setattr(
        "backend.apps.bot.services._send_with_retry", fake_send_with_retry
    )
    monkeypatch.setattr("backend.apps.bot.services.get_bot", lambda: object())
    monkeypatch.setattr(
        "backend.apps.bot.services.get_reminder_service", lambda: DummyReminder()
    )

    await status_service.set_status_test1_completed(candidate.telegram_id)

    dt_utc = datetime.now(timezone.utc) + timedelta(days=1)
    result = await schedule_manual_candidate_slot(
        candidate=candidate,
        recruiter=recruiter,
        city=city,
        dt_utc=dt_utc,
        slot_tz=city.tz,
    )

    assert result.status == "pending_offer"
    assert result.slot is not None

    async with async_session() as session:
        refreshed = await session.get(candidate_models.User, candidate.id)
        assert refreshed.candidate_status == CandidateStatus.SLOT_PENDING

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
        initial_status=CandidateStatus.TEST1_COMPLETED,  # Ready for interview scheduling
    )

    async with async_session() as session:
        city = models.City(name=f"City {telegram_id}", tz=city_tz, active=True)
        recruiter = models.Recruiter(
            name=f"Recruiter {telegram_id}", tz=city_tz, active=True
        )
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

    return candidate, city, recruiter


@pytest.mark.asyncio
async def test_schedule_manual_slot_handles_naive_conflicts():
    candidate, city, recruiter = await _setup_candidate_recruiter(telegram_id=101001)
    base_dt = (datetime.now(timezone.utc) + timedelta(days=2)).replace(
        minute=0, second=0, microsecond=0
    )

    async with async_session() as session:
        conflict_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=base_dt,
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        session.add(conflict_slot)
        await session.commit()

    dt_utc = base_dt - timedelta(minutes=5)

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
    base_dt = (datetime.now(timezone.utc) + timedelta(days=3)).replace(
        minute=30, second=0, microsecond=0
    )

    async with async_session() as session:
        conflict_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=base_dt,
            duration_min=60,
            status=models.SlotStatus.FREE,
        )
        session.add(conflict_slot)
        await session.commit()

    dt_utc = (base_dt - timedelta(minutes=5)).replace(tzinfo=None)

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

    async def fake_create_slot_assignment(*_args, **_kwargs):
        return SimpleNamespace(ok=True, message="ok")

    monkeypatch.setattr(
        "backend.domain.slot_assignment_service.create_slot_assignment",
        fake_create_slot_assignment,
    )

    dt_utc = (datetime.now(timezone.utc) + timedelta(days=4)).replace(
        hour=10,
        minute=0,
        second=0,
        microsecond=0,
    )
    result = await schedule_manual_candidate_slot(
        candidate=candidate,
        recruiter=recruiter,
        city=city,
        dt_utc=dt_utc,
        slot_tz=city.tz,
    )

    assert result.status == "pending_offer"

    async with async_session() as session:
        stored_slot = await session.scalar(
            select(models.Slot).where(models.Slot.recruiter_id == recruiter.id)
        )
        assert stored_slot is not None
        assert ensure_aware_utc(stored_slot.start_utc) == ensure_aware_utc(dt_utc)
