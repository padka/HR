#!/usr/bin/env python3
"""Test creating intro_day slot and notification."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus, OutboxNotification
from backend.domain.candidates.models import User
from backend.domain.repositories import add_outbox_notification
from sqlalchemy import select


async def test_create_intro_day():
    """Test creating intro_day slot with notification."""

    print("=" * 60)
    print("🧪 Testing Intro Day Slot Creation")
    print("=" * 60)
    print()

    # Find existing candidate
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .where(User.telegram_id == 837685732)
            .order_by(User.id.desc())
        )
        user = result.scalar_one_or_none()

        if not user:
            print("❌ Candidate not found!")
            return

        print(f"✅ Found candidate: {user.fio} (TG: {user.telegram_id})")

        # Find city and recruiter
        result = await session.execute(
            select(City)
            .where(City.name == user.city)
        )
        city = result.scalar_one_or_none()

        if not city:
            print(f"❌ City '{user.city}' not found!")
            return

        print(f"✅ Found city: {city.name}")

        # Get recruiter for this city
        result = await session.execute(
            select(Recruiter)
            .join(Recruiter.cities)
            .where(City.id == city.id, Recruiter.active == True)
        )
        recruiter = result.scalar_one_or_none()

        if not recruiter:
            print(f"❌ No active recruiter for city '{city.name}'!")
            return

        print(f"✅ Found recruiter: {recruiter.name}")
        print()

    # Create intro_day slot
    print("📅 Creating intro_day slot...")

    slot_time = datetime.now(timezone.utc) + timedelta(days=2)

    async with async_session() as session:
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            purpose="intro_day",
            tz_name=city.tz,
            start_utc=slot_time,
            status=SlotStatus.BOOKED,
            candidate_tg_id=user.telegram_id,
            candidate_fio=user.fio,
            candidate_tz=city.tz,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        slot_id = slot.id
        print(f"   ✅ Slot created: ID {slot_id}")
        print()

    # Create notification
    print("📬 Creating notification...")

    try:
        outbox_entry = await add_outbox_notification(
            notification_type="intro_day_invitation",
            booking_id=slot_id,
            candidate_tg_id=user.telegram_id,
            payload={},
        )

        print(f"   ✅ Notification created!")
        print(f"      ID: {outbox_entry.id}")
        print(f"      Type: {outbox_entry.type}")
        print(f"      Status: {outbox_entry.status}")
        print(f"      Booking ID: {outbox_entry.booking_id}")
        print(f"      Candidate TG ID: {outbox_entry.candidate_tg_id}")

    except Exception as e:
        print(f"   ❌ Failed to create notification!")
        print(f"      Error: {e}")
        import traceback
        traceback.print_exc()

    print()

    # Check that it was created
    print("🔍 Verifying notification in database...")

    async with async_session() as session:
        result = await session.execute(
            select(OutboxNotification)
            .where(
                OutboxNotification.booking_id == slot_id,
                OutboxNotification.type == "intro_day_invitation"
            )
        )
        notification = result.scalar_one_or_none()

        if notification:
            print(f"   ✅ Notification found in database!")
            print(f"      ID: {notification.id}")
            print(f"      Status: {notification.status}")
        else:
            print(f"   ❌ Notification NOT found in database!")

    print()
    print("=" * 60)
    print("✅ Test complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_create_intro_day())
