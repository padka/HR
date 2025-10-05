import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.apps.bot.reminders import ReminderKind, ReminderService, create_scheduler
from backend.apps.bot.state_store import build_state_manager
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_reminder_service_schedules_and_reschedules(monkeypatch):
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)
    service.start()

    async with async_session() as session:
        recruiter = models.Recruiter(name="Scheduler", tz="Europe/Moscow", active=True)
        city = models.City(name="Scheduler City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=30),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=777,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    try:
        await service.schedule_for_slot(slot_id)
        jobs = {job.id: job for job in scheduler.get_jobs()}
        assert len(jobs) >= 1
        assert f"slot:{slot_id}:{ReminderKind.REMIND_24H.value}" in jobs
        assert f"slot:{slot_id}:{ReminderKind.CONFIRM_6H.value}" in jobs
        assert f"slot:{slot_id}:{ReminderKind.CONFIRM_2H.value}" in jobs
        assert f"slot:{slot_id}:{ReminderKind.REMIND_1H.value}" in jobs
        assert all("remind_30m" not in job_id for job_id in jobs)

        # Reschedule after moving the slot
        async with async_session() as session:
            slot = await session.get(models.Slot, slot_id)
            slot.start_utc = datetime.now(timezone.utc) + timedelta(hours=48)
            await session.commit()

        await service.schedule_for_slot(slot_id)
        jobs_after = {job.id: job for job in scheduler.get_jobs()}
        assert len(jobs_after) >= 1
        job24 = jobs_after[f"slot:{slot_id}:{ReminderKind.REMIND_24H.value}"]
        assert job24.next_run_time > datetime.now(timezone.utc)

    finally:
        await service.shutdown()


@pytest.mark.asyncio
async def test_reminder_service_survives_restart(monkeypatch):
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)
    service.start()

    async with async_session() as session:
        recruiter = models.Recruiter(name="Restart", tz="Europe/Moscow", active=True)
        city = models.City(name="Restart City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=10),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=888,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    await service.schedule_for_slot(slot_id)
    await service.shutdown()

    # New scheduler instance should rebuild jobs from DB records
    scheduler2 = create_scheduler(redis_url=None)
    service2 = ReminderService(scheduler=scheduler2)
    service2.start()
    await service2.sync_jobs()

    try:
        jobs = scheduler2.get_jobs()
        assert any(job.id.startswith(f"slot:{slot_id}") for job in jobs)
    finally:
        await service2.shutdown()


@pytest.mark.asyncio
async def test_reminders_sent_immediately_for_past_targets(monkeypatch):
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)
    service.start()

    async with async_session() as session:
        recruiter = models.Recruiter(name="Immediate", tz="Europe/Moscow", active=True)
        city = models.City(name="Immediate City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(minutes=45),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=999,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    triggered: list[tuple[int, ReminderKind]] = []

    async def fake_execute(slot_id: int, kind: ReminderKind) -> None:
        triggered.append((slot_id, kind))

    monkeypatch.setattr(service, "_execute_job", fake_execute)

    try:
        await service.schedule_for_slot(slot_id)
        kinds = {kind for _slot_id, kind in triggered if _slot_id == slot_id}
        assert ReminderKind.CONFIRM_2H in kinds
        assert ReminderKind.REMIND_1H in kinds
        assert ReminderKind.CONFIRM_6H not in kinds
        assert ReminderKind.REMIND_24H not in kinds
        # No future jobs remain because everything should have fired immediately
        assert scheduler.get_jobs() == []
    finally:
        await service.shutdown()
