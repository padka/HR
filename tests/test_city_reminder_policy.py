"""Tests for per-city reminder policy service."""

import pytest

from backend.apps.admin_ui.services.city_reminder_policy import (
    GLOBAL_DEFAULTS,
    delete_city_reminder_policy,
    get_city_reminder_policy,
    upsert_city_reminder_policy,
)
from backend.core.db import async_session
from backend.domain.models import City


@pytest.fixture
async def test_city():
    async with async_session() as session:
        city = City(name="PolicyTestCity", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        city_id = city.id

    yield city_id

    await delete_city_reminder_policy(city_id)
    async with async_session() as session:
        row = await session.get(City, city_id)
        if row:
            await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_get_returns_global_defaults_when_no_custom_policy(test_city):
    policy = await get_city_reminder_policy(test_city)
    assert policy.is_custom is False
    assert policy.quiet_hours_start == GLOBAL_DEFAULTS.quiet_hours_start
    assert policy.confirm_6h_enabled is True


@pytest.mark.asyncio
async def test_upsert_creates_custom_policy(test_city):
    policy = await upsert_city_reminder_policy(
        test_city,
        confirm_6h_enabled=False,
        quiet_hours_start=20,
        quiet_hours_end=9,
    )
    assert policy.is_custom is True
    assert policy.confirm_6h_enabled is False
    assert policy.quiet_hours_start == 20
    assert policy.quiet_hours_end == 9
    # Unset fields should keep defaults
    assert policy.confirm_2h_enabled is True


@pytest.mark.asyncio
async def test_get_returns_custom_policy_after_upsert(test_city):
    await upsert_city_reminder_policy(
        test_city,
        intro_remind_3h_enabled=False,
        quiet_hours_start=21,
        quiet_hours_end=7,
    )
    policy = await get_city_reminder_policy(test_city)
    assert policy.is_custom is True
    assert policy.intro_remind_3h_enabled is False
    assert policy.quiet_hours_start == 21


@pytest.mark.asyncio
async def test_delete_resets_to_global_defaults(test_city):
    await upsert_city_reminder_policy(test_city, confirm_6h_enabled=False)
    deleted = await delete_city_reminder_policy(test_city)
    assert deleted is True

    policy = await get_city_reminder_policy(test_city)
    assert policy.is_custom is False
    assert policy.confirm_6h_enabled is True  # back to global default


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_false():
    deleted = await delete_city_reminder_policy(999_999)
    assert deleted is False


@pytest.mark.asyncio
async def test_quiet_hours_clamped_to_valid_range(test_city):
    policy = await upsert_city_reminder_policy(
        test_city,
        quiet_hours_start=25,  # > 23, should clamp
        quiet_hours_end=-1,    # < 0, should clamp
    )
    assert 0 <= policy.quiet_hours_start <= 23
    assert 0 <= policy.quiet_hours_end <= 23
