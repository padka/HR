from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.apps.bot.services import handle_recruiter_identity_command
from backend.core.db import async_session
from backend.domain import models
from backend.domain.repositories import (
    approve_slot,
    get_active_recruiters,
    get_active_recruiters_for_city,
    get_candidate_cities,
    get_city,
    get_city_by_name,
    city_has_available_slots,
    find_city_by_plain_name,
    get_free_slots_by_recruiter,
    get_recruiter,
    get_slot,
    reserve_slot,
    reject_slot,
    set_recruiter_chat_id_by_command,
)


@pytest.mark.asyncio
async def test_recruiter_and_city_queries():
    async with async_session() as session:
        recruiter_active = models.Recruiter(name="Михаил", tz="Europe/Moscow", active=True)
        recruiter_inactive = models.Recruiter(name="Иван", tz="Europe/Moscow", active=False)
        city = models.City(name="Москва", tz="Europe/Moscow", active=True)
        recruiter_active.cities.append(city)
        session.add_all([recruiter_active, recruiter_inactive, city])
        await session.commit()
        await session.refresh(recruiter_active)
        await session.refresh(recruiter_inactive)
        await session.refresh(city)

    active = await get_active_recruiters()
    assert [r.name for r in active] == ["Михаил"]

    by_city = await get_active_recruiters_for_city(city.id)
    assert [r.name for r in by_city] == ["Михаил"]

    fetched = await get_recruiter(recruiter_active.id)
    assert fetched is not None
    assert fetched.name == "Михаил"

    city_by_name = await get_city_by_name("Москва")
    assert city_by_name is not None
    assert city_by_name.id == city.id

    city_by_id = await get_city(city.id)
    assert city_by_id.name == "Москва"


@pytest.mark.asyncio
async def test_city_helpers_cover_casefold_and_slots():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        recruiter = models.Recruiter(name="Рекрутёр", tz="Europe/Moscow", active=True)
        city = models.City(name="г. Волгоград", tz="Europe/Volgograd", active=True)
        recruiter.cities.append(city)
        session.add_all([recruiter, city])
        await session.flush()

        session.add(
            models.Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=now + timedelta(hours=3),
                status=models.SlotStatus.FREE,
            )
        )
        await session.commit()
        await session.refresh(city)

    found = await find_city_by_plain_name("волгоград (центр)")
    assert found is not None
    assert found.id == city.id

    assert await city_has_available_slots(city.id) is True


@pytest.mark.asyncio
async def test_city_recruiter_lookup_includes_slot_owners():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        responsible = models.Recruiter(name="Ответственный", tz="Europe/Moscow", active=True)
        extra = models.Recruiter(name="Помощник", tz="Europe/Moscow", active=True)
        city = models.City(name="Казань", tz="Europe/Moscow", active=True)
        responsible.cities.append(city)
        session.add_all([responsible, extra, city])
        await session.flush()

        session.add(
            models.Slot(
                recruiter_id=extra.id,
                city_id=city.id,
                start_utc=now + timedelta(hours=2),
                status=models.SlotStatus.FREE,
            )
        )

        await session.commit()
        await session.refresh(responsible)
        await session.refresh(extra)
        await session.refresh(city)

    recruiters = await get_active_recruiters_for_city(city.id)
    names = {r.name for r in recruiters}
    assert names == {"Ответственный", "Помощник"}


@pytest.mark.asyncio
async def test_candidate_cities_fallback_returns_active_entries():
    async with async_session() as session:
        city = models.City(name="Курск", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()

    cities = await get_candidate_cities()
    assert [c.name_plain for c in cities] == ["Курск"]





@pytest.mark.asyncio
async def test_iam_command_updates_recruiter_chat_id():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Софья", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    responses = []

    class DummyMessage:
        def __init__(self, text: str, chat_id: int) -> None:
            self.text = text
            self.chat = SimpleNamespace(id=chat_id)
            self.from_user = SimpleNamespace(id=chat_id)

        async def answer(self, text: str, **kwargs) -> None:
            responses.append(text)

    message = DummyMessage("/iam Софья", chat_id=987654321)

    await handle_recruiter_identity_command(message)

    async with async_session() as session:
        updated = await session.get(models.Recruiter, recruiter_id)
        assert updated is not None
        assert updated.tg_chat_id == 987654321

    assert any("Готово" in resp for resp in responses)
