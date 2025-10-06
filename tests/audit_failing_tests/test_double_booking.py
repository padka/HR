from datetime import datetime, timedelta, timezone

import pytest

from backend.core.db import async_session
from backend.domain import models
from backend.domain.models import SlotStatus
from backend.domain.repositories import (
    approve_slot,
    confirm_slot_by_candidate,
    reserve_slot,
)


@pytest.mark.asyncio
async def test_confirmed_candidate_cannot_double_book_same_recruiter():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Алексей", tz="Europe/Moscow", active=True)
        city = models.City(name="Самара", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot_one = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=10),
            status=SlotStatus.FREE,
        )
        slot_two = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=12),
            status=SlotStatus.FREE,
        )
        session.add_all([slot_one, slot_two])
        await session.commit()
        await session.refresh(slot_one)
        await session.refresh(slot_two)

        slot_one_id = slot_one.id
        slot_two_id = slot_two.id

    reservation = await reserve_slot(
        slot_one_id,
        candidate_tg_id=555,
        candidate_fio="Двойник",
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
    )
    assert reservation.status == "reserved"

    await approve_slot(slot_one_id)
    confirm_result = await confirm_slot_by_candidate(slot_one_id)
    assert confirm_result.status == "confirmed"

    second_reservation = await reserve_slot(
        slot_two_id,
        candidate_tg_id=555,
        candidate_fio="Двойник",
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
    )

    assert second_reservation.status != "reserved", "Кандидат с подтверждённым слотом не должен бронировать повторно"
