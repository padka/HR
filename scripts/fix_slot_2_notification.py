#!/usr/bin/env python3
"""Fix notification for slot 2 by creating a new one."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.db import async_session
from backend.domain.models import OutboxNotification
from backend.domain.repositories import add_outbox_notification
from sqlalchemy import update


async def fix_slot_2():
    """Fix notification for slot 2."""

    print("=" * 60)
    print("🔧 Fixing Slot 2 Notification")
    print("=" * 60)
    print()

    slot_id = 2
    candidate_tg_id = 837685732

    # Step 1: Reset old notification to pending
    print("1️⃣ Resetting intro_day_invitation to pending...")

    async with async_session() as session:
        reset_update = (
            update(OutboxNotification)
            .where(
                OutboxNotification.candidate_tg_id == candidate_tg_id,
                OutboxNotification.type == "intro_day_invitation",
                OutboxNotification.booking_id == slot_id,
            )
            .values(
                status="pending",
                attempts=0,
                next_retry_at=None,
                locked_at=None,
                last_error=None,
            )
        )
        result = await session.execute(reset_update)
        await session.commit()

        updated_count = result.rowcount
        print(f"   ✅ Reset {updated_count} notification(s) to pending")
        print()

    # Step 2: Create new notification
    print("2️⃣ Creating new notification...")

    try:
        outbox_entry = await add_outbox_notification(
            notification_type="intro_day_invitation",
            booking_id=slot_id,
            candidate_tg_id=candidate_tg_id,
            payload={},
        )

        print(f"   ✅ Notification created!")
        print(f"      ID: {outbox_entry.id}")
        print(f"      Type: {outbox_entry.type}")
        print(f"      Status: {outbox_entry.status}")
        print(f"      Booking ID: {outbox_entry.booking_id}")
        print()

    except Exception as e:
        print(f"   ❌ Failed to create notification!")
        print(f"      Error: {e}")
        import traceback
        traceback.print_exc()
        return

    print("=" * 60)
    print("✅ Fix complete!")
    print()
    print("🔍 Next steps:")
    print("   1. Wait 3-5 seconds for NotificationService to process")
    print("   2. Run: ENVIRONMENT=development REDIS_URL=\\\"\\\" .venv/bin/python scripts/diagnose_notifications.py")
    print("   3. Check that notification was sent")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(fix_slot_2())
