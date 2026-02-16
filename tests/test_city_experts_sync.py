from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.apps.admin_ui.services.cities import update_city_settings
from backend.core.db import async_session
from backend.domain import models
from backend.domain.cities.models import CityExpert


@pytest.mark.asyncio
async def test_update_city_settings_syncs_city_experts_from_text():
    async with async_session() as session:
        city = models.City(name="City", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        city_id = city.id

    error, _, _ = await update_city_settings(
        city_id,
        name="City",
        recruiter_ids=[],
        responsible_id=None,
        criteria=None,
        experts="Alice\nBob",
        plan_week=None,
        plan_month=None,
        tz="Europe/Moscow",
        active=True,
    )
    assert error is None

    async with async_session() as session:
        experts = (
            await session.scalars(select(CityExpert).where(CityExpert.city_id == city_id).order_by(CityExpert.id))
        ).all()
        assert [e.name for e in experts] == ["Alice", "Bob"]
        assert [e.is_active for e in experts] == [True, True]


@pytest.mark.asyncio
async def test_update_city_settings_syncs_city_experts_from_items_and_archives_missing():
    async with async_session() as session:
        city = models.City(name="City2", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        city_id = city.id

    # Seed from legacy text.
    error, _, _ = await update_city_settings(
        city_id,
        name="City2",
        recruiter_ids=[],
        responsible_id=None,
        criteria=None,
        experts="Alice\nBob",
        plan_week=None,
        plan_month=None,
        tz="Europe/Moscow",
        active=True,
    )
    assert error is None

    async with async_session() as session:
        seeded = (
            await session.scalars(select(CityExpert).where(CityExpert.city_id == city_id).order_by(CityExpert.id))
        ).all()
        assert len(seeded) == 2
        alice_id = seeded[0].id

    # Now provide explicit items (Bob omitted => should be archived).
    error, _, _ = await update_city_settings(
        city_id,
        name="City2",
        recruiter_ids=[],
        responsible_id=None,
        criteria=None,
        experts=None,
        experts_items=[
            {"id": alice_id, "name": "Alice", "is_active": True},
            {"name": "Charlie", "is_active": True},
        ],
        plan_week=None,
        plan_month=None,
        tz="Europe/Moscow",
        active=True,
    )
    assert error is None

    async with async_session() as session:
        experts = (
            await session.scalars(select(CityExpert).where(CityExpert.city_id == city_id).order_by(CityExpert.id))
        ).all()
        names = [e.name for e in experts]
        actives = {e.name: e.is_active for e in experts}
        assert names == ["Alice", "Bob", "Charlie"]
        assert actives["Alice"] is True
        assert actives["Charlie"] is True
        assert actives["Bob"] is False

        city = await session.get(models.City, city_id)
        assert city is not None
        assert city.experts == "Alice\nCharlie"

