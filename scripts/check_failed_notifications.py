#!/usr/bin/env python3
"""Check failed notifications in detail."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.db import async_session
from backend.domain.models import OutboxNotification
from sqlalchemy import select


async def check_failed():
    """Check failed notifications."""

    print("=" * 60)
    print("🔍 Failed Notifications Analysis")
    print("=" * 60)
    print()

    async with async_session() as session:
        # Get all failed notifications
        result = await session.execute(
            select(OutboxNotification)
            .where(OutboxNotification.status == "failed")
            .order_by(OutboxNotification.created_at.desc())
            .limit(30)
        )
        failed_notifications = result.scalars().all()

        if not failed_notifications:
            print("✅ No failed notifications found!")
            return

        print(f"Found {len(failed_notifications)} failed notifications")
        print()

        # Group by error type
        errors = {}
        for notif in failed_notifications:
            error_key = notif.last_error or "unknown"
            if error_key not in errors:
                errors[error_key] = []
            errors[error_key].append(notif)

        print("📊 Errors by type:")
        for error, notifs in sorted(errors.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"\n   {error}: {len(notifs)} notifications")
            for notif in notifs[:3]:  # Show first 3 examples
                print(f"      ID: {notif.id}")
                print(f"         Type: {notif.type}")
                print(f"         Booking ID: {notif.booking_id}")
                print(f"         Candidate TG ID: {notif.candidate_tg_id}")
                print(f"         Attempts: {notif.attempts}")
                print(f"         Created: {notif.created_at}")
                print(f"         Last error: {notif.last_error}")
                print()

        # Check for intro_day_invitation failures
        print("=" * 60)
        print("🔍 Intro Day Invitation Failures")
        print("=" * 60)
        print()

        intro_day_failed = [n for n in failed_notifications if n.type == "intro_day_invitation"]

        if intro_day_failed:
            print(f"Found {len(intro_day_failed)} failed intro_day_invitation notifications:")
            for notif in intro_day_failed:
                print(f"\n   ID: {notif.id}")
                print(f"      Booking ID: {notif.booking_id}")
                print(f"      Candidate TG ID: {notif.candidate_tg_id}")
                print(f"      Attempts: {notif.attempts}")
                print(f"      Created: {notif.created_at}")
                print(f"      Last error: {notif.last_error}")
        else:
            print("✅ No failed intro_day_invitation notifications")

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(check_failed())
