import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from backend.apps.bot.metrics import (
    get_reminder_metrics_snapshot,
    reset_reminder_metrics,
)
from backend.apps.bot.reminders import ReminderKind, ReminderService, create_scheduler
from backend.apps.bot.state_store import build_state_manager
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_reminder_service_schedules_and_reschedules(monkeypatch):
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)
    service.start()

    candidate_zone = ZoneInfo("Europe/Moscow")
    far_future_local = (datetime.now(candidate_zone) + timedelta(days=3)).replace(
        hour=13,
        minute=0,
        second=0,
        microsecond=0,
    )
    start_utc = far_future_local.astimezone(timezone.utc)

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
            start_utc=start_utc,
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
        expected = {
            f"slot:{slot_id}:{ReminderKind.REMIND_24H.value}",
            f"slot:{slot_id}:{ReminderKind.CONFIRM_6H.value}",
            f"slot:{slot_id}:{ReminderKind.CONFIRM_2H.value}",
        }
        assert set(jobs) == expected

        # Reschedule after moving the slot
        async with async_session() as session:
            slot = await session.get(models.Slot, slot_id)
            new_start_local = far_future_local + timedelta(days=1)
            slot.start_utc = new_start_local.astimezone(timezone.utc)
            await session.commit()

        await service.schedule_for_slot(slot_id)
        jobs_after = {job.id: job for job in scheduler.get_jobs()}
        assert set(jobs_after) == expected
        confirm_job = jobs_after[f"slot:{slot_id}:{ReminderKind.CONFIRM_2H.value}"]
        assert confirm_job.next_run_time > datetime.now(timezone.utc)

    finally:
        await service.shutdown()


@pytest.mark.asyncio
async def test_quiet_hours_adjustment_and_metrics():
    await reset_reminder_metrics()
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)
    service.start()

    candidate_zone = ZoneInfo("Europe/Moscow")
    start_local = (datetime.now(candidate_zone) + timedelta(days=2)).replace(
        hour=6,
        minute=30,
        second=0,
        microsecond=0,
    )
    start_utc = start_local.astimezone(timezone.utc)

    async with async_session() as session:
        recruiter = models.Recruiter(name="Quiet", tz="Europe/Moscow", active=True)
        city = models.City(name="Quiet City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=start_utc,
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=2024,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    try:
        await service.schedule_for_slot(slot_id)
        jobs = {job.id: job for job in scheduler.get_jobs()}
        assert f"slot:{slot_id}:{ReminderKind.CONFIRM_2H.value}" in jobs
        confirm_job = jobs[f"slot:{slot_id}:{ReminderKind.CONFIRM_2H.value}"]
        run_local = confirm_job.next_run_time.astimezone(candidate_zone)
        assert run_local.date() == (start_local.date() - timedelta(days=1))
        assert run_local.hour == 21
        assert run_local.minute == 59

        snapshot = await get_reminder_metrics_snapshot()
        assert snapshot.adjusted_total.get(ReminderKind.CONFIRM_2H.value, 0) == 1
        assert ReminderKind.REMIND_1H.value not in snapshot.adjusted_total
        assert snapshot.scheduled_total.get(ReminderKind.REMIND_24H.value, 0) >= 1
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
        assert ReminderKind.CONFIRM_6H not in kinds
        assert ReminderKind.REMIND_24H in kinds
        assert scheduler.get_jobs() == []
    finally:
        await service.shutdown()


@pytest.mark.asyncio
async def test_schedule_can_skip_confirmation_prompts(monkeypatch):
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)
    service.start()

    async with async_session() as session:
        recruiter = models.Recruiter(name="Skip", tz="Europe/Moscow", active=True)
        city = models.City(name="Skip City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=3),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=111,
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
        await service.schedule_for_slot(
            slot_id, skip_confirmation_prompts=True
        )
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert f"slot:{slot_id}:{ReminderKind.CONFIRM_2H.value}" not in job_ids
        assert all(kind != ReminderKind.CONFIRM_2H for _, kind in triggered)
        assert all(kind != ReminderKind.CONFIRM_6H for _, kind in triggered)
        assert any(kind == ReminderKind.REMIND_24H for _, kind in triggered)
        assert not job_ids
    finally:
        await service.shutdown()


@pytest.mark.asyncio
async def test_execute_job_enqueues_outbox_notification(monkeypatch):
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)

    async with async_session() as session:
        recruiter = models.Recruiter(name="Broker", tz="Europe/Moscow", active=True)
        city = models.City(name="Broker City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=5),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=333,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    class _FakeNotificationService:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int]] = []

        async def _enqueue_outbox(self, outbox_id: int, attempt: int = 0) -> None:
            self.calls.append((outbox_id, attempt))

    fake_service = _FakeNotificationService()

    monkeypatch.setattr("backend.apps.bot.services.get_notification_service", lambda: fake_service)

    await service._execute_job(slot_id, ReminderKind.REMIND_24H)

    assert fake_service.calls, "Expected reminder to enqueue outbox notification"
    outbox_id, attempt = fake_service.calls[0]
    assert attempt == 0

    async with async_session() as session:
        outbox = await session.get(models.OutboxNotification, outbox_id)
        assert outbox is not None
        assert outbox.type == "slot_reminder"
        assert outbox.payload_json.get("reminder_kind") == ReminderKind.REMIND_24H.value

    await service.shutdown()


def test_schedule_respects_non_canonical_timezone():
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)

    messy_tz = " asia/novosibirsk "
    start_utc = datetime(2025, 2, 1, 9, 0, tzinfo=timezone.utc)

    reminders = service._build_schedule(start_utc, messy_tz)

    assert reminders
    local_zone = reminders[0].run_at_local.tzinfo
    assert local_zone is not None
    assert getattr(local_zone, "key", str(local_zone)) == "Asia/Novosibirsk"
