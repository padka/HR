import asyncio
import calendar
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from backend.apps.bot.reminders import (
    ReminderKind,
    ReminderService,
    _ensure_aware,
    create_scheduler,
)
from backend.apps.bot.state_store import build_state_manager
from backend.core.db import async_session
from backend.domain import models
from sqlalchemy import select


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


def _next_fall_back_local() -> datetime:
    tz = ZoneInfo("Europe/Berlin")
    now_year = datetime.now(timezone.utc).year
    year = now_year + 1
    # find last Sunday in October for the chosen year
    month_matrix = calendar.monthcalendar(year, 10)
    last_week = month_matrix[-1]
    if last_week[calendar.SUNDAY] == 0:
        last_week = month_matrix[-2]
    day = last_week[calendar.SUNDAY]
    # 02:30 local time during the transition (ambiguous time)
    return datetime(year, 10, day, 2, 30, tzinfo=tz)


@pytest.mark.asyncio
async def test_reminder_service_preserves_local_offsets_through_dst():
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)
    service.start()

    async with async_session() as session:
        recruiter = models.Recruiter(name="DST", tz="Europe/Moscow", active=True)
        city = models.City(name="DST City", tz="Europe/Berlin", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        start_local = _next_fall_back_local()
        start_utc = start_local.astimezone(timezone.utc)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=start_utc,
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=4242,
            candidate_tz="Europe/Berlin",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    try:
        await service.schedule_for_slot(slot_id)
        jobs = scheduler.get_jobs()
        assert jobs, "expected reminder jobs to be scheduled"

        expected_offsets = {
            ReminderKind.REMIND_24H.value: timedelta(hours=24),
            ReminderKind.CONFIRM_6H.value: timedelta(hours=6),
            ReminderKind.REMIND_2H.value: timedelta(hours=2),
            ReminderKind.REMIND_30M.value: timedelta(minutes=30),
        }
        start_local = start_utc.astimezone(ZoneInfo("Europe/Berlin"))

        for job in jobs:
            kind = job.id.split(":")[-1]
            if kind not in expected_offsets:
                continue
            run = job.next_run_time
            assert run.tzinfo == timezone.utc
            run_local = run.astimezone(ZoneInfo("Europe/Berlin"))
            assert start_local - run_local == expected_offsets[kind]

        async with async_session() as session:
            rows = await session.execute(
                select(models.SlotReminderJob).where(models.SlotReminderJob.slot_id == slot_id)
            )
            stored_jobs = rows.scalars().all()
            assert stored_jobs, "expected persisted reminder jobs"
            job_lookup = {
                job.id.split(":")[-1]: job
                for job in jobs
                if job.id and job.id.startswith(f"slot:{slot_id}:")
            }
            for stored in stored_jobs:
                stored_utc = _ensure_aware(stored.scheduled_at)
                assert stored_utc.tzinfo == timezone.utc
                job = job_lookup.get(stored.kind)
                if job is not None:
                    assert stored_utc == job.next_run_time
    finally:
        await service.shutdown()
