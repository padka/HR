#!/usr/bin/env python3
"""Check if notification was created for slot ID 2."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.db import async_session
from backend.domain.models import OutboxNotification, Slot
from sqlalchemy import select


async def check_slot_notification():
    """Check notification for slot 2."""

    print("=" * 60)
    print("🔍 Checking Slot ID 2 Notification")
    print("=" * 60)
    print()

    slot_id = 2

    async with async_session() as session:
        # Get the slot
        slot = await session.get(Slot, slot_id)

        if not slot:
            print(f"❌ Slot {slot_id} not found!")
            return

        print(f"📅 Slot {slot_id} details:")
        print(f"   Purpose: {slot.purpose}")
        print(f"   Status: {slot.status}")
        print(f"   Candidate: {slot.candidate_fio} (TG: {slot.candidate_tg_id})")
        print(f"   Time: {slot.start_utc}")
        print(f"   Created: {slot.created_at}")
        print()

        # Check for notifications
        result = await session.execute(
            select(OutboxNotification)
            .where(OutboxNotification.booking_id == slot_id)
            .order_by(OutboxNotification.created_at.desc())
        )
        notifications = result.scalars().all()

        if not notifications:
            print(f"❌ NO NOTIFICATIONS found for slot {slot_id}!")
            print()
            print("🔍 This is the problem! Notification was not created when intro_day slot was assigned.")
            print()
            print("Possible causes:")
            print("1. Exception in candidates_schedule_intro_day_submit()")
            print("2. add_outbox_notification() was not called")
            print("3. Exception was silently caught")
            return

        print(f"📬 Found {len(notifications)} notification(s) for slot {slot_id}:")
        print()

        for notif in notifications:
            print(f"   ID: {notif.id}")
            print(f"      Type: {notif.type}")
            print(f"      Status: {notif.status}")
            print(f"      Candidate TG ID: {notif.candidate_tg_id}")
            print(f"      Attempts: {notif.attempts}")
            print(f"      Created: {notif.created_at}")
            print(f"      Last error: {notif.last_error}")
            print()

            if notif.status == "sent":
                print(f"   ✅ Notification was successfully sent!")
            elif notif.status == "pending":
                print(f"   ⏳ Notification is pending (will be sent soon)")
            elif notif.status == "failed":
                print(f"   ❌ Notification FAILED!")
                print(f"      Reason: {notif.last_error}")

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(check_slot_notification())
