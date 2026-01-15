"""Seed 40 test candidates and attach them to recruiters via slots.

Usage:
  PYTHONPATH=. python scripts/seed_test_candidates.py

Creates users if they do not exist (by telegram_id) and creates booked slots
assigned to recruiters in round-robin manner. Safe to rerun: skips existing
telegram_ids and existing slots for the same candidate at the same start time.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.models import Slot, SlotStatus, Recruiter, City
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus

TOTAL_CANDIDATES = 40
TG_BASE = 900_000_000  # offset for synthetic telegram IDs


async def seed():
    async with async_session() as session:
        recruiters: List[Recruiter] = list((await session.scalars(select(Recruiter))).all())
        if not recruiters:
            print("No recruiters found; aborting.")
            return

        cities: List[City] = list((await session.scalars(select(City))).all())
        city_id = cities[0].id if cities else None

        created_users = 0
        created_slots = 0
        now = datetime.now(timezone.utc)

        for idx in range(1, TOTAL_CANDIDATES + 1):
            tg_id = TG_BASE + idx
            user = await session.scalar(select(User).where(User.telegram_id == tg_id))
            if not user:
                user = User(
                    telegram_id=tg_id,
                    username=f"testcand{idx}",
                    telegram_user_id=tg_id,
                    telegram_username=f"testcand{idx}",
                    fio=f"Тестовый кандидат {idx}",
                    city="TestCity",
                    desired_position="Test position",
                    is_active=True,
                    candidate_status=CandidateStatus.INTERVIEW_SCHEDULED,
                    status_changed_at=now,
                    last_activity=now,
                )
                session.add(user)
                created_users += 1
            recruiter = recruiters[(idx - 1) % len(recruiters)]
            start_utc = now + timedelta(days=idx // 5, hours=idx % 8)
            existing_slot = await session.scalar(
                select(Slot).where(
                    Slot.recruiter_id == recruiter.id,
                    Slot.start_utc == start_utc,
                    Slot.candidate_tg_id == tg_id,
                )
            )
            if existing_slot:
                continue
            slot = Slot(
                recruiter_id=recruiter.id,
                city_id=city_id,
                candidate_city_id=city_id,
                purpose="interview",
                tz_name=recruiter.tz if getattr(recruiter, "tz", None) else "Europe/Moscow",
                start_utc=start_utc,
                duration_min=60,
                status=SlotStatus.BOOKED,
                candidate_tg_id=tg_id,
                candidate_fio=user.fio,
                candidate_tz=getattr(recruiter, "tz", None) or "Europe/Moscow",
            )
            session.add(slot)
            created_slots += 1

        await session.commit()
        print(f"Seed complete: users created={created_users}, slots created={created_slots}")


if __name__ == "__main__":
    asyncio.run(seed())
