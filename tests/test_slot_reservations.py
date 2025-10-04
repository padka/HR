import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from backend.core.db import async_session
from backend.domain import models
from backend.domain.repositories import reserve_slot, ReservationResult


@pytest.mark.asyncio
async def test_reserve_slot_prevents_duplicate_pending():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        recruiter = models.Recruiter(name="Ольга", tz="Europe/Moscow", active=True)
        city = models.City(name="Тюмень", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slots = [
            models.Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=now + timedelta(hours=idx + 1),
                status=models.SlotStatus.FREE,
            )
            for idx in range(2)
        ]
        session.add_all(slots)
        await session.commit()
        for slot in slots:
            await session.refresh(slot)

    first = await reserve_slot(
        slots[0].id,
        candidate_tg_id=123,
        candidate_fio="Кандидат",
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
    )
    assert first.status == "reserved"

    second = await reserve_slot(
        slots[1].id,
        candidate_tg_id=123,
        candidate_fio="Кандидат",
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
    )
    assert second.status in {"duplicate_candidate", "already_reserved"}


@pytest.mark.asyncio
async def test_reserve_slot_idempotent_within_window():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        recruiter = models.Recruiter(name="Ирина", tz="Europe/Moscow", active=True)
        city = models.City(name="Ярославль", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=1),
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

    first = await reserve_slot(
        slot.id,
        candidate_tg_id=777,
        candidate_fio="Кандидат",
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
    )
    assert first.status == "reserved"

    second = await reserve_slot(
        slot.id,
        candidate_tg_id=777,
        candidate_fio="Кандидат",
        candidate_tz="Europe/Moscow",
        candidate_city_id=city.id,
        expected_recruiter_id=recruiter.id,
        expected_city_id=city.id,
    )
    assert second.status == "already_reserved"
    assert second.slot is not None
    assert second.slot.id == slot.id


@pytest.mark.asyncio
async def test_reserve_slot_concurrent_requests():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        recruiter = models.Recruiter(name="Елена", tz="Europe/Moscow", active=True)
        city = models.City(name="Воронеж", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slots = []
        for idx in range(2):
            slot = models.Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=now + timedelta(hours=idx + 1),
                status=models.SlotStatus.FREE,
            )
            session.add(slot)
            slots.append(slot)
        await session.commit()
        for slot in slots:
            await session.refresh(slot)

    async def attempt(slot_id: int) -> ReservationResult:
        return await reserve_slot(
            slot_id,
            candidate_tg_id=555,
            candidate_fio="Кандидат",
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
            expected_recruiter_id=recruiter.id,
            expected_city_id=city.id,
        )

    results = await asyncio.gather(*(attempt(slot.id) for slot in slots))
    reserved_count = sum(1 for res in results if res.status == "reserved")
    assert reserved_count == 1
    assert any(res.status in {"duplicate_candidate", "already_reserved"} for res in results)


@pytest.mark.asyncio
async def test_unique_index_enforced():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        recruiter = models.Recruiter(name="Антон", tz="Europe/Moscow", active=True)
        city = models.City(name="Сочи", tz="Europe/Moscow", active=True)
        slot_a = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=1),
            status=models.SlotStatus.PENDING,
            candidate_tg_id=321,
        )
        slot_b = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=2),
            status=models.SlotStatus.PENDING,
            candidate_tg_id=321,
        )
        session.add_all([recruiter, city, slot_a, slot_b])
        with pytest.raises(IntegrityError):
            await session.commit()
