import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from aiogram.exceptions import TelegramRetryAfter, TelegramServerError
from aiogram.methods import SendMessage
from sqlalchemy import func, select

from backend.apps.bot.broker import InMemoryNotificationBroker
from backend.apps.bot.metrics import (
    get_reminder_metrics_snapshot,
    reset_reminder_metrics,
)
from backend.apps.bot.reminders import ReminderKind, ReminderService, create_scheduler
from backend.apps.bot.services import NotificationService
from backend.apps.bot.state_store import build_state_manager
from backend.core.db import async_session
from backend.domain import models
from backend.domain.models import MessageTemplate
from backend.domain.repositories import add_outbox_notification, get_outbox_item


class DummyBucket:
    def __init__(self) -> None:
        self.calls = 0

    async def consume(self, tokens: float = 1.0) -> None:
        self.calls += 1


class FakeRetryAfter(TelegramRetryAfter):
    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        self.message = f"retry after {retry_after}"
        self.args = (self.message,)


async def _ensure_message_template(key: str) -> None:
    async with async_session() as session:
        existing = await session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.key == key,
                MessageTemplate.locale == "ru",
                MessageTemplate.channel == "tg",
            )
        )
        if existing:
            return
        template = MessageTemplate(
            key=key,
            locale="ru",
            channel="tg",
            body_md="Напоминание {candidate_name}",
            version=1,
            is_active=True,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(template)
        await session.commit()


async def _create_booked_slot(*, candidate_id: int = 4321) -> models.Slot:
    async with async_session() as session:
        recruiter = models.Recruiter(
            name="Reminder Recruiter",
            tz="Europe/Moscow",
            active=True,
            telemost_url="https://telemost.example",
        )
        city = models.City(name="Reminder City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=6),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=candidate_id,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        return slot


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
            f"slot:{slot_id}:{ReminderKind.CONFIRM_6H.value}",
            f"slot:{slot_id}:{ReminderKind.CONFIRM_3H.value}",
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

        # For early morning slots (6:30 AM), all reminders (6h→0:00, 3h→3:00, 2h→4:00)
        # fall into quiet hours and get adjusted to 21:30 previous day.
        # Duplicate prevention keeps only the first (6h), skips 3h and 2h.
        assert f"slot:{slot_id}:{ReminderKind.CONFIRM_6H.value}" in jobs
        confirm_job = jobs[f"slot:{slot_id}:{ReminderKind.CONFIRM_6H.value}"]
        run_local = confirm_job.next_run_time.astimezone(candidate_zone)
        assert run_local.date() == (start_local.date() - timedelta(days=1))
        assert run_local.hour == 21
        assert run_local.minute == 30

        snapshot = await get_reminder_metrics_snapshot()
        assert snapshot.scheduled_total.get(ReminderKind.CONFIRM_6H.value, 0) >= 1
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
        assert scheduler.get_jobs() == []
    finally:
        await service.shutdown()


@pytest.mark.asyncio
async def test_reminder_retry_backoff_on_channel_failure(monkeypatch):
    await _ensure_message_template("confirm_2h")
    slot = await _create_booked_slot()
    outbox_entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot.id,
        candidate_tg_id=slot.candidate_tg_id,
        payload={"reminder_kind": ReminderKind.CONFIRM_2H.value},
    )
    item = await get_outbox_item(outbox_entry.id)
    broker = InMemoryNotificationBroker()
    await broker.start()
    service = NotificationService(
        broker=broker,
        poll_interval=0.05,
        batch_size=1,
        rate_limit_per_sec=2.0,
        retry_base_delay=20,
        retry_max_delay=40,
    )
    bucket = DummyBucket()
    service._token_bucket = bucket
    jitter_factor = 1.12
    monkeypatch.setattr("backend.apps.bot.services.random.uniform", lambda a, b: jitter_factor)
    dummy_bot = SimpleNamespace()
    monkeypatch.setattr("backend.apps.bot.services.get_bot", lambda: dummy_bot)

    async def failing_send(bot, method, correlation_id):
        raise TelegramServerError("channel down")

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", failing_send)

    await service._process_interview_reminder(item)

    async with async_session() as session:
        entry = await session.get(models.OutboxNotification, outbox_entry.id)
        assert entry is not None
        assert entry.status == "pending"
        assert entry.next_retry_at is not None
        next_retry = entry.next_retry_at
        if next_retry.tzinfo is None:
            next_retry = next_retry.replace(tzinfo=timezone.utc)
        delay = (next_retry - datetime.now(timezone.utc)).total_seconds()
    expected = service._retry_base * jitter_factor
    assert delay >= expected - 1.0
    assert bucket.calls == 1
    await service.shutdown()


@pytest.mark.asyncio
async def test_reminder_retry_honors_retry_after_hint(monkeypatch):
    await _ensure_message_template("confirm_2h")
    slot = await _create_booked_slot(candidate_id=9898)
    outbox_entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot.id,
        candidate_tg_id=slot.candidate_tg_id,
        payload={"reminder_kind": ReminderKind.CONFIRM_2H.value},
    )
    item = await get_outbox_item(outbox_entry.id)
    broker = InMemoryNotificationBroker()
    await broker.start()
    service = NotificationService(
        broker=broker,
        poll_interval=0.05,
        batch_size=1,
        rate_limit_per_sec=1.0,
        retry_base_delay=10,
        retry_max_delay=40,
    )
    bucket = DummyBucket()
    service._token_bucket = bucket
    monkeypatch.setattr("backend.apps.bot.services.random.uniform", lambda a, b: 1.0)
    dummy_bot = SimpleNamespace()
    monkeypatch.setattr("backend.apps.bot.services.get_bot", lambda: dummy_bot)

    async def rate_limited_send(bot, method, correlation_id):
        raise FakeRetryAfter(retry_after=12)

    monkeypatch.setattr("backend.apps.bot.services._send_with_retry", rate_limited_send)

    await service._process_interview_reminder(item)

    async with async_session() as session:
        entry = await session.get(models.OutboxNotification, outbox_entry.id)
        assert entry is not None
        assert entry.next_retry_at is not None
        next_retry = entry.next_retry_at
        if next_retry.tzinfo is None:
            next_retry = next_retry.replace(tzinfo=timezone.utc)
        delay = (next_retry - datetime.now(timezone.utc)).total_seconds()
    assert delay >= 12 - 0.5
    assert bucket.calls == 1
    await service.shutdown()


@pytest.mark.asyncio
async def test_intro_day_gets_three_hour_reminder(monkeypatch):
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)
    service.start()

    async with async_session() as session:
        recruiter = models.Recruiter(name="Intro", tz="Europe/Moscow", active=True)
        city = models.City(name="Intro City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=12),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=3030,
            candidate_tz="Europe/Moscow",
            purpose="intro_day",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    try:
        await service.schedule_for_slot(slot_id)
        jobs = {job.id for job in scheduler.get_jobs()}
        expected_job = f"slot:{slot_id}:{ReminderKind.INTRO_REMIND_3H.value}"
        assert jobs == {expected_job}
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
        assert not triggered
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

    await service._execute_job(slot_id, ReminderKind.CONFIRM_6H)

    assert fake_service.calls, "Expected reminder to enqueue outbox notification"
    outbox_id, attempt = fake_service.calls[0]
    assert attempt == 0

    async with async_session() as session:
        outbox = await session.get(models.OutboxNotification, outbox_id)
        assert outbox is not None
        assert outbox.type == "slot_reminder"
        assert outbox.payload_json.get("reminder_kind") == ReminderKind.CONFIRM_6H.value

    await service.shutdown()


@pytest.mark.asyncio
async def test_execute_job_skips_when_policy_disables_kind(monkeypatch):
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)

    async with async_session() as session:
        recruiter = models.Recruiter(name="Policy", tz="Europe/Moscow", active=True)
        city = models.City(name="Policy City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=4),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=3434,
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

    async def _disabled_policy():
        return (
            {
                "interview": {
                    "confirm_6h": {"enabled": False, "offset_hours": 6},
                    "confirm_3h": {"enabled": True, "offset_hours": 3},
                    "confirm_2h": {"enabled": True, "offset_hours": 2},
                },
                "intro_day": {"intro_remind_3h": {"enabled": True, "offset_hours": 3}},
                "min_time_before_immediate_hours": 2,
            },
            None,
        )

    monkeypatch.setattr("backend.apps.bot.services.get_notification_service", lambda: fake_service)
    monkeypatch.setattr("backend.apps.bot.reminders.get_reminder_policy_config", _disabled_policy)

    await service._execute_job(slot_id, ReminderKind.CONFIRM_6H)

    assert not fake_service.calls

    async with async_session() as session:
        outbox_count = await session.scalar(
            select(func.count())
            .select_from(models.OutboxNotification)
            .where(models.OutboxNotification.booking_id == slot_id)
            .where(models.OutboxNotification.type == "slot_reminder")
        )
    assert outbox_count == 0

    await service.shutdown()


def test_schedule_respects_non_canonical_timezone():
    scheduler = create_scheduler(redis_url=None)
    service = ReminderService(scheduler=scheduler)

    messy_tz = " asia/novosibirsk "
    start_utc = datetime(2025, 2, 1, 9, 0, tzinfo=timezone.utc)

    reminders = service._build_schedule(start_utc, messy_tz, "interview")

    assert reminders
    local_zone = reminders[0].run_at_local.tzinfo
    assert local_zone is not None
    assert getattr(local_zone, "key", str(local_zone)) == "Asia/Novosibirsk"
