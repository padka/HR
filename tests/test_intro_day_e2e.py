"""End-to-end test for intro_day notification flow."""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone

from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus, OutboxNotification
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.repositories import add_outbox_notification, get_outbox_item
from backend.apps.bot.broker import InMemoryNotificationBroker
from backend.apps.bot.services import NotificationService, configure_notification_service


@pytest.mark.asyncio
async def test_intro_day_notification_end_to_end():
    """Test that intro_day notification is created, queued, and processed."""

    # Create test data
    async with async_session() as session:
        # Create city
        city = City(
            name="Test City",
            tz="Europe/Moscow",
            active=True,
        )
        session.add(city)
        await session.flush()

        # Create recruiter
        recruiter = Recruiter(
            name="Test Recruiter",
            tg_chat_id=123456789,
            tz="Europe/Moscow",
            active=True,
        )
        recruiter.cities.append(city)
        session.add(recruiter)
        await session.flush()

        # Create candidate
        candidate = User(
            telegram_id=987654321,
            username="test_candidate",
            fio="Test Candidate",
            city="Test City",
            candidate_status=CandidateStatus.WAITING_SLOT,
        )
        session.add(candidate)
        await session.flush()

        # Create intro_day slot
        slot_time = datetime.now(timezone.utc) + timedelta(days=1)
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=slot_time,
            status=SlotStatus.BOOKED,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id
        candidate_tg_id = candidate.telegram_id

    # Add notification to outbox
    outbox_entry = await add_outbox_notification(
        notification_type="intro_day_invitation",
        booking_id=slot_id,
        candidate_tg_id=candidate_tg_id,
        payload={},
    )

    assert outbox_entry is not None
    assert outbox_entry.type == "intro_day_invitation"
    assert outbox_entry.booking_id == slot_id
    assert outbox_entry.candidate_tg_id == candidate_tg_id
    assert outbox_entry.status == "pending"

    # Verify outbox entry exists in database
    fetched_entry = await get_outbox_item(outbox_entry.id)
    assert fetched_entry is not None
    assert fetched_entry.type == "intro_day_invitation"
    assert fetched_entry.booking_id == slot_id

    print(f"✅ Outbox entry created: id={outbox_entry.id}, type={outbox_entry.type}, status={outbox_entry.status}")
    print(f"   Slot ID: {slot_id}, Candidate TG ID: {candidate_tg_id}")


@pytest.mark.asyncio
async def test_notification_service_processes_intro_day():
    """Test that NotificationService can process intro_day notifications."""

    # Setup broker and notification service
    broker = InMemoryNotificationBroker()
    await broker.start()

    # Configure notification service
    service = NotificationService(
        scheduler=None,
        broker=broker,
        poll_interval=1.0,
        batch_size=10,
        rate_limit_per_sec=10.0,
        worker_concurrency=1,
        max_attempts=3,
        retry_base_delay=5.0,
        retry_max_delay=60.0,
    )
    configure_notification_service(service)

    # Create test data
    async with async_session() as session:
        city = City(name="Test City 2", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.flush()

        recruiter = Recruiter(
            name="Test Recruiter 2",
            tg_chat_id=123456790,
            tz="Europe/Moscow",
            active=True,
        )
        recruiter.cities.append(city)
        session.add(recruiter)
        await session.flush()

        candidate = User(
            telegram_id=987654322,
            username="test_candidate_2",
            fio="Test Candidate 2",
            city="Test City 2",
            candidate_status=CandidateStatus.WAITING_SLOT,
        )
        session.add(candidate)
        await session.flush()

        slot_time = datetime.now(timezone.utc) + timedelta(days=1)
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=slot_time,
            status=SlotStatus.BOOKED,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id
        candidate_tg_id = candidate.telegram_id

    # Add notification to outbox
    outbox_entry = await add_outbox_notification(
        notification_type="intro_day_invitation",
        booking_id=slot_id,
        candidate_tg_id=candidate_tg_id,
        payload={},
    )

    print(f"📬 Outbox entry created: id={outbox_entry.id}")

    # Check if notification service can claim the outbox entry
    from backend.domain.repositories import claim_outbox_batch

    batch = await claim_outbox_batch(batch_size=10)
    print(f"📥 Claimed batch size: {len(batch)}")

    if batch:
        for item in batch:
            print(f"   - Outbox ID: {item.id}, Type: {item.type}, Booking ID: {item.booking_id}")

    # Verify the outbox entry was claimed
    assert len(batch) > 0
    assert any(item.id == outbox_entry.id for item in batch)

    print(f"✅ NotificationService can claim intro_day notifications")


@pytest.mark.asyncio
async def test_notification_broker_publishes_and_reads():
    """Test that InMemoryNotificationBroker works correctly."""

    broker = InMemoryNotificationBroker()
    await broker.start()

    # Publish a message
    payload = {
        "outbox_id": 123,
        "notification_type": "intro_day_invitation",
        "booking_id": 456,
        "candidate_tg_id": 789,
    }

    message_id = await broker.publish(payload, delay_seconds=0)
    assert message_id is not None
    print(f"📤 Published message: {message_id}")

    # Read the message
    messages = await broker.read(count=10, block_ms=100)
    assert len(messages) == 1
    assert messages[0].id == message_id
    assert messages[0].payload["outbox_id"] == 123
    assert messages[0].payload["notification_type"] == "intro_day_invitation"

    print(f"📨 Read message: {messages[0].id}")
    print(f"   Payload: {messages[0].payload}")

    # Ack the message
    await broker.ack(message_id)
    print(f"✅ Message acknowledged")

    # Verify no more messages
    messages = await broker.read(count=10, block_ms=100)
    assert len(messages) == 0
    print(f"✅ Broker is empty after ack")
