from __future__ import annotations

import pytest

from backend.core.db import async_session
from backend.domain.models import City
from backend.domain.repositories import resolve_city_id_and_tz_by_plain_name


@pytest.mark.asyncio
async def test_resolve_city_by_plain_name_handles_prefixes_and_separators():
    async with async_session() as session:
        city = City(name="Екатеринбург", tz="Asia/Yekaterinburg", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)

    city_id, tz = await resolve_city_id_and_tz_by_plain_name("г. Екатеринбург")
    assert city_id == city.id
    assert tz == "Asia/Yekaterinburg"

    city_id2, _tz2 = await resolve_city_id_and_tz_by_plain_name("город Екатеринбург")
    assert city_id2 == city.id

    city_id3, _tz3 = await resolve_city_id_and_tz_by_plain_name("Екатеринбург (центр)")
    assert city_id3 == city.id

    city_id4, _tz4 = await resolve_city_id_and_tz_by_plain_name("Екатеринбург / Удалённо")
    assert city_id4 == city.id


@pytest.mark.asyncio
async def test_resolve_city_by_plain_name_normalizes_yo_to_e():
    async with async_session() as session:
        city = City(name="Орёл", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)

    city_id, tz = await resolve_city_id_and_tz_by_plain_name("Орел")
    assert city_id == city.id
    assert tz == "Europe/Moscow"

