from datetime import datetime, timedelta, timezone

import pytest
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from backend.apps.bot.broker import BrokerMessage, InMemoryNotificationBroker
from backend.apps.bot.services import NotificationService
from backend.core.db import async_session
from backend.domain.models import NotificationLog, OutboxNotification, Recruiter, Slot, SlotStatus
from backend.domain.repositories import OutboxItem, add_outbox_notification


@pytest.mark.asyncio
async def test_retry_marks_failed_when_exceeds_max_attempts():
    now = datetime.now(timezone.utc) + timedelta(hours=4)
    async with async_session() as session:
        recruiter = Recruiter(name="Notif Rec", tg_chat_id=987654321, tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.flush()
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            candidate_city_id=None,
            purpose="interview",
            tz_name="Europe/Moscow",
            start_utc=now,
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_tg_id=777001,
            candidate_fio="Notif User",
        )
        session.add(slot)
        await session.commit()

    entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot.id,
        candidate_tg_id=slot.candidate_tg_id,
        payload={"msg": "hi"},
    )
    item = OutboxItem(
        id=entry.id,
        booking_id=entry.booking_id,
        type=entry.type,
        payload=entry.payload_json or {},
        candidate_tg_id=entry.candidate_tg_id,
        recruiter_tg_id=entry.recruiter_tg_id,
        attempts=entry.attempts,
        created_at=entry.created_at,
    )

    service = NotificationService(
        scheduler=AsyncIOScheduler(jobstores={"default": MemoryJobStore()}, timezone="UTC"),
        broker=InMemoryNotificationBroker(),
        max_attempts=1,
    )
    service._current_message = BrokerMessage(id="msg-1", payload={"attempt": 1, "max_attempts": 1})

    await service._schedule_retry(
        item,
        attempt=1,
        log_type="slot_reminder",
        notification_type="slot_reminder",
        error="boom",
        rendered=None,
        candidate_tg_id=slot.candidate_tg_id,
    )

    async with async_session() as session:
        log = await session.scalar(select(NotificationLog).where(NotificationLog.booking_id == slot.id))
    assert log is not None
    assert log.last_error is not None
