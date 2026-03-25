from datetime import datetime, timedelta, timezone

import pytest
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from backend.apps.admin_ui.services.notifications_ops import retry_outbox_notification
from backend.apps.bot.broker import BrokerMessage, InMemoryNotificationBroker
from backend.apps.bot.services import NotificationService
from backend.core.db import async_session
from backend.core.messenger.channel_state import (
    get_messenger_channel_health,
    mark_messenger_channel_healthy,
    set_messenger_channel_degraded,
)
from backend.domain.models import NotificationLog, OutboxNotification, Recruiter, Slot, SlotStatus
from backend.domain.repositories import (
    OutboxItem,
    add_outbox_notification,
    claim_outbox_batch,
)


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


@pytest.mark.asyncio
async def test_claim_outbox_batch_skips_degraded_channels():
    telegram_entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=None,
        candidate_tg_id=7001,
        payload={"msg": "telegram"},
        messenger_channel="telegram",
    )
    max_entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=None,
        candidate_tg_id=7002,
        payload={"msg": "max"},
        messenger_channel="max",
    )

    try:
        await set_messenger_channel_degraded("max", reason="max:invalid_token")
        claimed = await claim_outbox_batch(batch_size=10)

        claimed_ids = {item.id for item in claimed}
        assert telegram_entry.id in claimed_ids
        assert max_entry.id not in claimed_ids
    finally:
        await mark_messenger_channel_healthy("max")


@pytest.mark.asyncio
async def test_retry_outbox_notification_requeues_dead_letter_and_keeps_channel_degraded():
    entry = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=None,
        candidate_tg_id=7101,
        payload={"msg": "max"},
        messenger_channel="max",
    )

    async with async_session() as session:
        stored = await session.get(OutboxNotification, entry.id)
        assert stored is not None
        stored.status = "dead_letter"
        stored.attempts = 3
        stored.last_error = "invalid token"
        stored.failure_class = "misconfiguration"
        stored.failure_code = "invalid_token"
        stored.provider_message_id = "provider-1"
        stored.dead_lettered_at = datetime.now(timezone.utc)
        await session.commit()

    await set_messenger_channel_degraded("max", reason="max:invalid_token")

    ok, reason = await retry_outbox_notification(entry.id)
    assert ok is True
    assert reason is None

    async with async_session() as session:
        refreshed = await session.get(OutboxNotification, entry.id)

    assert refreshed is not None
    assert refreshed.status == "pending"
    assert refreshed.attempts == 0
    assert refreshed.last_error is None
    assert refreshed.failure_class is None
    assert refreshed.failure_code is None
    assert refreshed.provider_message_id is None
    assert refreshed.dead_lettered_at is None

    channel_health = await get_messenger_channel_health()
    assert channel_health["max"]["status"] == "degraded"
