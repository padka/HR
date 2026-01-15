from datetime import date

import pytest

from backend.apps.admin_ui.services.slots import generate_default_day_slots, list_slots
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, SlotStatus


@pytest.mark.asyncio
async def test_generate_default_day_creates_slots_visible_in_list():
    day = date(2025, 1, 2)
    async with async_session() as session:
        city = City(name="Gen City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Generator", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        rec_id, city_id = recruiter.id, city.id
        city_name = city.name
        city_tz = city.tz
        session.expunge_all()  # Detach all objects before closing session

    created = await generate_default_day_slots(recruiter_id=rec_id, day=day, city_id=city_id)
    assert created == 48

    result = await list_slots(
        rec_id,
        status=None,
        page=1,
        per_page=100,
        search_query=None,
        city_name=city_name,
        day=day,
    )
    assert result["total"] == 48
    slots = result["items"]
    assert all(slot.city_id == city_id for slot in slots)
    assert all(getattr(slot, "purpose") == "interview" for slot in slots)
    assert all((slot.status == SlotStatus.FREE or str(slot.status).lower() == "free") for slot in slots)
    assert all(slot.tz_name == city_tz for slot in slots)


@pytest.mark.asyncio
async def test_generate_default_day_auto_city_uses_first_recruiter_city():
    day = date(2025, 2, 3)
    async with async_session() as session:
        city = City(name="Auto City", tz="Europe/Samara", active=True)
        recruiter = Recruiter(name="Auto Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        rec_id, city_id = recruiter.id, city.id
        city_name = city.name
        city_tz = city.tz
        session.expunge_all()  # Detach all objects before closing session

    created = await generate_default_day_slots(recruiter_id=rec_id, day=day, city_id=None)
    assert created == 48

    result = await list_slots(
        rec_id,
        status=None,
        page=1,
        per_page=10,
        search_query=None,
        city_name=city_name,
        day=day,
    )
    slots = result["items"]
    assert slots, "Generated slots should be visible in list"
    assert slots[0].city_id == city_id
    assert slots[0].tz_name == city_tz
