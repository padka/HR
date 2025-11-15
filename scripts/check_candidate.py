#!/usr/bin/env python3
"""Check candidate details."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.db import async_session
from backend.domain.candidates.models import User
from sqlalchemy import select


async def check_candidate():
    """Check candidate with fio 'Романов Роман Романович'."""

    print("=" * 60)
    print("🔍 Checking Candidate")
    print("=" * 60)
    print()

    async with async_session() as session:
        # Find candidate by fio
        result = await session.execute(
            select(User)
            .where(User.fio.like("%Романов%"))
            .order_by(User.id.desc())
        )
        candidates = result.scalars().all()

        if not candidates:
            print("❌ No candidates found with 'Романов' in name")
            return

        print(f"Found {len(candidates)} candidate(s):")
        print()

        for user in candidates:
            print(f"ID: {user.id}")
            print(f"   Name: {user.fio}")
            print(f"   Username: {user.username}")
            print(f"   Telegram ID: {user.telegram_id}")
            print(f"   City: {user.city}")
            print(f"   Status: {user.candidate_status}")
            print(f"   Created: {user.last_activity}")
            print()

            if user.telegram_id is None:
                print("   ❌ TELEGRAM_ID IS NULL!")
                print("   This is why notification cannot be sent!")
            elif user.telegram_id == 837685732:
                print("   ✅ Telegram ID matches slot")

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(check_candidate())
