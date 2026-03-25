from __future__ import annotations

import pytest

from backend.apps.admin_ui.services.cities import invalidate_city_caches, update_city_settings
from backend.apps.bot.city_registry import list_candidate_cities
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.models import City
from backend.domain.repositories import invalidate_city_lookup_cache, resolve_city_id_and_tz_by_plain_name


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


@pytest.mark.asyncio
async def test_city_rename_invalidates_lookup_and_bot_city_cache(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    await invalidate_city_lookup_cache()
    try:
        async with async_session() as session:
            city = City(name="Самара", tz="Europe/Moscow", active=True)
            candidate = User(
                fio="Кандидат Самара",
                city="Самара",
                source="seed",
            )
            session.add_all([city, candidate])
            await session.commit()
            await session.refresh(city)
            await session.refresh(candidate)
            candidate_id = candidate.id

        resolved_id, resolved_tz = await resolve_city_id_and_tz_by_plain_name("Самара")
        assert resolved_id == city.id
        assert resolved_tz == "Europe/Moscow"

        initial_cities = await list_candidate_cities()
        assert [city_info.name_plain for city_info in initial_cities] == ["Самара"]

        error, updated_city, _ = await update_city_settings(
            city.id,
            name="Самара Центр",
            recruiter_ids=[],
            criteria=None,
            experts=None,
            plan_week=None,
            plan_month=None,
            tz=None,
            active=None,
        )

        assert error is None
        assert updated_city is not None
        assert updated_city.name_plain == "Самара Центр"

        old_id, old_tz = await resolve_city_id_and_tz_by_plain_name("Самара")
        assert old_id is None
        assert old_tz is None

        new_id, new_tz = await resolve_city_id_and_tz_by_plain_name("Самара Центр")
        assert new_id == city.id
        assert new_tz == "Europe/Moscow"

        refreshed_cities = await list_candidate_cities()
        assert [city_info.name_plain for city_info in refreshed_cities] == ["Самара Центр"]

        async with async_session() as session:
            updated_candidate = await session.get(User, candidate_id)
            assert updated_candidate is not None
            assert updated_candidate.city == "Самара Центр"
    finally:
        await invalidate_city_caches()
