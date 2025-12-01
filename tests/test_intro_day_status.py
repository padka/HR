import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from backend.domain.repositories import confirm_slot_by_candidate
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import Slot, SlotStatus
from backend.core.db import async_session


@pytest.mark.asyncio
async def test_intro_day_confirmation_updates_status():
    candidate_id = 555001
    async with async_session() as session:
        user = User(
            telegram_id=candidate_id,
            fio="Intro Candidate",
            city="Тест",
            candidate_status=CandidateStatus.INTRO_DAY_SCHEDULED,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        slot = Slot(
            recruiter_id=1,
            city_id=None,
            candidate_city_id=None,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=datetime.now(timezone.utc) + timedelta(hours=4),
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_tg_id=candidate_id,
            candidate_fio="Intro Candidate",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

    result = await confirm_slot_by_candidate(slot.id)
    assert result.status == "confirmed"

    async with async_session() as session:
        updated = await session.scalar(select(User).where(User.telegram_id == candidate_id))
        assert updated is not None
        assert updated.candidate_status == CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY
