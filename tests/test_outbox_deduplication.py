"""Tests for outbox notification deduplication.

Regression test for bug where sent notifications were being re-enqueued,
causing duplicate messages to be sent to users.
"""

import pytest
from datetime import datetime, timezone

from backend.core.db import async_session
from backend.domain.models import OutboxNotification, Slot, Recruiter, City, SlotStatus
from backend.domain.repositories import add_outbox_notification, update_outbox_entry


@pytest.mark.asyncio
async def test_add_outbox_notification_is_idempotent_for_sent_entries():
    """
    Test that add_outbox_notification is idempotent for sent entries.

    When trying to create a notification that already exists with status='sent',
    the function should return the existing entry WITHOUT modifying it.
    This prevents IntegrityError and ensures idempotency.
    """
    # Create test slot
    async with async_session() as session:
        city = City(name="Test City", tz="UTC", active=True)
        recruiter = Recruiter(name="Test Recruiter", tz="UTC", active=True)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_tg_id=123456789,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id
        candidate_id = slot.candidate_tg_id

    # Create first outbox entry (simulating first CONFIRM_2H reminder)
    entry1 = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot_id,
        candidate_tg_id=candidate_id,
        payload={"reminder_kind": "confirm_2h"},
    )

    assert entry1.status == "pending"
    entry1_id = entry1.id

    # Mark it as sent (simulating successful delivery)
    await update_outbox_entry(
        entry1_id,
        status="sent",
        attempts=1,
        last_error=None,
        next_retry_at=None,
    )

    # Verify it's marked as sent
    async with async_session() as session:
        sent_entry = await session.get(OutboxNotification, entry1_id)
        assert sent_entry is not None
        assert sent_entry.status == "sent"

    # Create second outbox entry with same parameters
    # This simulates what happens when reject_booking is called twice
    entry2 = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot_id,
        candidate_tg_id=candidate_id,
        payload={"reminder_kind": "confirm_2h"},
    )

    # CRITICAL: Should return the SAME entry (idempotent behavior)
    assert entry2.id == entry1_id, "Should return existing sent entry (idempotent)"
    assert entry2.status == "sent", "Status should remain 'sent'"

    # Verify that the entry is still marked as sent
    async with async_session() as session:
        sent_entry = await session.get(OutboxNotification, entry1_id)
        assert sent_entry is not None
        assert sent_entry.status == "sent", "Entry should remain sent"

    # Verify there is only 1 entry in the database (no duplicate created)
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(OutboxNotification).where(
                OutboxNotification.booking_id == slot_id,
                OutboxNotification.type == "slot_reminder",
            )
        )
        all_entries = result.scalars().all()
        assert len(all_entries) == 1, "Should have only 1 entry (idempotent)"
        assert all_entries[0].status == "sent"
        assert all_entries[0].id == entry1_id


@pytest.mark.asyncio
async def test_add_outbox_notification_reuses_pending_entries():
    """
    Verify that add_outbox_notification DOES reuse pending entries.

    This is the expected behavior - if an entry is still pending,
    we should update it rather than create a duplicate.
    """
    # Create test slot
    async with async_session() as session:
        city = City(name="Test City", tz="UTC", active=True)
        recruiter = Recruiter(name="Test Recruiter", tz="UTC", active=True)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_tg_id=123456789,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id
        candidate_id = slot.candidate_tg_id

    # Create first outbox entry
    entry1 = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot_id,
        candidate_tg_id=candidate_id,
        payload={"reminder_kind": "confirm_2h"},
    )

    assert entry1.status == "pending"
    entry1_id = entry1.id

    # Create second entry with same parameters while first is still pending
    entry2 = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot_id,
        candidate_tg_id=candidate_id,
        payload={"reminder_kind": "confirm_2h"},
    )

    # Should reuse the existing pending entry
    assert entry2.id == entry1_id, "Should reuse existing pending entry"
    assert entry2.status == "pending"

    # Verify there's only 1 entry in the database
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(OutboxNotification).where(
                OutboxNotification.booking_id == slot_id,
                OutboxNotification.type == "slot_reminder",
            )
        )
        all_entries = result.scalars().all()
        assert len(all_entries) == 1, "Should have only 1 entry (reused)"


@pytest.mark.asyncio
async def test_add_outbox_notification_different_types_are_separate():
    """
    Verify that different notification types create separate entries.

    Even if booking_id and candidate_tg_id are the same, different types
    should create separate entries.
    """
    # Create test slot
    async with async_session() as session:
        city = City(name="Test City", tz="UTC", active=True)
        recruiter = Recruiter(name="Test Recruiter", tz="UTC", active=True)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc),
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_tg_id=123456789,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id
        candidate_id = slot.candidate_tg_id

    # Create entries with different types
    entry1 = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot_id,
        candidate_tg_id=candidate_id,
        payload={"reminder_kind": "confirm_6h"},
    )

    entry2 = await add_outbox_notification(
        notification_type="slot_reminder",
        booking_id=slot_id,
        candidate_tg_id=candidate_id,
        payload={"reminder_kind": "confirm_2h"},
    )

    # Both should exist as separate entries
    # (Different payloads don't make them different in the dedup logic)
    # Actually, they have the same notification_type, so they should reuse
    assert entry2.id == entry1.id, "Same type should reuse entry"

    # But if we use truly different types:
    entry3 = await add_outbox_notification(
        notification_type="interview_confirmed_candidate",
        booking_id=slot_id,
        candidate_tg_id=candidate_id,
    )

    assert entry3.id != entry1.id, "Different types should create separate entries"

    # Verify we have 2 entries
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(OutboxNotification).where(
                OutboxNotification.booking_id == slot_id,
            )
        )
        all_entries = result.scalars().all()
        assert len(all_entries) == 2
