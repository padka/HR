from datetime import date, datetime, timezone, timedelta

import pytest
from zoneinfo import ZoneInfo

from backend.apps.admin_ui.services.slots import generate_default_day_slots, list_slots
from backend.apps.bot.services import slot_local_labels
from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot


@pytest.mark.asyncio
async def test_generate_default_day_stores_utc_times():
    target_day = date(2025, 12, 1)
    async with async_session() as session:
        city = City(name="TZ City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="TZ Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        rec_id = recruiter.id
        city_id = city.id

    created = await generate_default_day_slots(recruiter_id=rec_id, day=target_day, city_id=city_id)
    assert created == 48

    async with async_session() as session:
        slots = (
            await session.execute(
                Slot.__table__.select().where(
                    Slot.recruiter_id == rec_id,
                    Slot.city_id == city_id,
                )
            )
        ).all()
    assert slots, "slots must be created"
    first_start = slots[0].start_utc.replace(tzinfo=timezone.utc)
    # 09:00 MSK == 06:00 UTC in December
    assert first_start.hour == 6 and first_start.minute == 0
    assert first_start.date() == target_day


@pytest.mark.asyncio
async def test_candidate_sees_local_time_labels():
    dt_utc = datetime(2025, 12, 1, 7, 0, tzinfo=timezone.utc)  # 10:00 MSK
    labels_nsk = slot_local_labels(dt_utc, "Asia/Novosibirsk")
    labels_ekb = slot_local_labels(dt_utc, "Asia/Yekaterinburg")
    labels_almaty = slot_local_labels(dt_utc, "Asia/Almaty")

    assert labels_nsk["slot_time_local"] == "14:00"
    assert labels_ekb["slot_time_local"] == "12:00"
    assert labels_almaty["slot_time_local"] == "12:00"


@pytest.mark.asyncio
async def test_slots_list_date_filter_in_msk_range():
    target_day = date(2025, 12, 1)
    msk = ZoneInfo("Europe/Moscow")
    # Slot exactly at start of day in MSK (00:00) => 21:00 previous UTC day
    start_local = datetime.combine(target_day, datetime.min.time(), tzinfo=msk)
    start_utc = start_local.astimezone(timezone.utc)

    async with async_session() as session:
        city = City(name="Filter City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Filter Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id
        city_id = city.id
        city_tz = city.tz
        city_name = city.name
        slot = Slot(
            recruiter_id=recruiter_id,
            city_id=city_id,
            tz_name=city_tz,
            start_utc=start_utc,
            status="free",
        )
        session.add(slot)
        await session.commit()
        session.expunge_all()  # Detach all objects before closing session

    result = await list_slots(
        recruiter_id=None,
        status=None,
        page=1,
        per_page=10,
        search_query=None,
        city_name=city_name,
        day=target_day,
    )
    assert result["total"] == 1
