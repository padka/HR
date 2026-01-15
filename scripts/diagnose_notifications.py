#!/usr/bin/env python3
"""Diagnostic script to check notification system health."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.db import async_session
from backend.domain.models import OutboxNotification, Slot
from backend.domain.repositories import claim_outbox_batch, get_outbox_queue_depth
from backend.apps.bot.services import get_bot, NotificationNotConfigured
from sqlalchemy import select, func


async def diagnose():
    """Run diagnostic checks on notification system."""

    print("=" * 60)
    print("🔍 Notification System Diagnostics")
    print("=" * 60)
    print()

    # Check 1: Check if there are any outbox notifications
    print("📊 Checking outbox notifications...")
    async with async_session() as session:
        total_count = await session.scalar(
            select(func.count()).select_from(OutboxNotification)
        )
        pending_count = await session.scalar(
            select(func.count())
            .select_from(OutboxNotification)
            .where(OutboxNotification.status == "pending")
        )
        sent_count = await session.scalar(
            select(func.count())
            .select_from(OutboxNotification)
            .where(OutboxNotification.status == "sent")
        )
        failed_count = await session.scalar(
            select(func.count())
            .select_from(OutboxNotification)
            .where(OutboxNotification.status == "failed")
        )

        print(f"   Total outbox notifications: {total_count}")
        print(f"   Pending: {pending_count}")
        print(f"   Sent: {sent_count}")
        print(f"   Failed: {failed_count}")
        print()

        if pending_count > 0:
            print("📬 Pending notifications:")
            result = await session.execute(
                select(OutboxNotification)
                .where(OutboxNotification.status == "pending")
                .order_by(OutboxNotification.created_at.desc())
                .limit(10)
            )
            pending_notifications = result.scalars().all()

            for notif in pending_notifications:
                print(f"   ID: {notif.id}")
                print(f"      Type: {notif.type}")
                print(f"      Booking ID: {notif.booking_id}")
                print(f"      Candidate TG ID: {notif.candidate_tg_id}")
                print(f"      Attempts: {notif.attempts}")
                print(f"      Created: {notif.created_at}")
                print(f"      Next Retry: {notif.next_retry_at}")
                print(f"      Last Error: {notif.last_error}")
                print()

    # Check 2: Check if intro_day slots exist
    print("📅 Checking intro_day slots...")
    async with async_session() as session:
        intro_day_count = await session.scalar(
            select(func.count())
            .select_from(Slot)
            .where(Slot.purpose == "intro_day")
        )
        print(f"   Total intro_day slots: {intro_day_count}")

        if intro_day_count > 0:
            result = await session.execute(
                select(Slot)
                .where(Slot.purpose == "intro_day")
                .order_by(Slot.created_at.desc())
                .limit(5)
            )
            intro_slots = result.scalars().all()

            print("   Recent intro_day slots:")
            for slot in intro_slots:
                print(f"   ID: {slot.id}, Candidate: {slot.candidate_fio} (TG: {slot.candidate_tg_id})")
                print(f"      Status: {slot.status}, Time: {slot.start_utc}")
                print()

    # Check 3: Check if bot is configured
    print("🤖 Checking bot configuration...")
    try:
        bot = get_bot()
        print(f"   ✅ Bot is configured: {bot}")
        print(f"      Bot token: {bot.token[:10]}..." if bot.token else "No token")
    except RuntimeError as e:
        print(f"   ❌ Bot is NOT configured: {e}")
        print()

    # Check 4: Try to claim from outbox
    print("📥 Testing outbox claim...")
    try:
        batch = await claim_outbox_batch(batch_size=5)
        print(f"   Claimed {len(batch)} notifications")

        if batch:
            for item in batch:
                print(f"   - ID: {item.id}, Type: {item.type}, Booking: {item.booking_id}")
    except Exception as e:
        print(f"   ❌ Error claiming outbox: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)
    print("✅ Diagnostics complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(diagnose())
