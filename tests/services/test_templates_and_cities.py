import importlib.util

import pytest

if importlib.util.find_spec("sqlalchemy") is None:  # pragma: no cover - env guard
    pytest.skip("sqlalchemy is not installed in this environment", allow_module_level=True)

from backend.apps.admin_ui.services.cities import (
    api_city_owners_payload,
    update_city_settings,
)
from backend.apps.admin_ui.services.templates import api_templates_payload, update_template
from backend.core.db import async_session
from backend.domain import models
from backend.domain.template_stages import CITY_TEMPLATE_STAGES


@pytest.mark.asyncio
async def test_template_payloads_and_city_owner_assignment():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Owner", tz="Europe/Moscow", active=True)
        city = models.City(name="Owner City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

    stage_key = CITY_TEMPLATE_STAGES[0].key

    error = await update_city_settings(
        city_id=city.id,
        responsible_id=recruiter.id,
        templates={stage_key: "custom text"},
        criteria="Опыт продаж",
        experts="Эксперт А",
        plan_week=12,
        plan_month=48,
    )
    assert error is None

    async with async_session() as session:
        refreshed_city = await session.get(models.City, city.id)
        assert refreshed_city is not None
        assert refreshed_city.responsible_recruiter_id == recruiter.id
        assert refreshed_city.criteria == "Опыт продаж"
        assert refreshed_city.experts == "Эксперт А"
        assert refreshed_city.plan_week == 12
        assert refreshed_city.plan_month == 48

    owners_payload = await api_city_owners_payload()
    assert owners_payload["ok"]
    assert owners_payload["owners"][city.id] == recruiter.id

    template_payload = await api_templates_payload(city_id=city.id, key=stage_key)
    assert isinstance(template_payload, dict)
    assert template_payload.get("found") is True
    assert template_payload.get("text") == "custom text"


@pytest.mark.asyncio
async def test_update_city_settings_rolls_back_on_template_error():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Owner", tz="Europe/Moscow", active=True)
        city = models.City(name="Rollback City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

    error = await update_city_settings(
        city_id=city.id,
        responsible_id=recruiter.id,
        templates={"invalid_key": "should fail"},
        criteria="",
        experts="",
        plan_week=None,
        plan_month=None,
    )

    assert error is not None
    assert "Unknown template keys" in error

    async with async_session() as session:
        refreshed_city = await session.get(models.City, city.id)
        assert refreshed_city.responsible_recruiter_id is None
        await session.refresh(refreshed_city, attribute_names=["templates"])
    assert refreshed_city.templates == []


@pytest.mark.asyncio
async def test_update_city_settings_updates_core_fields():
    async with async_session() as session:
        city = models.City(name="Уфа", tz="Europe/Moscow", active=False)
        session.add(city)
        await session.commit()
        await session.refresh(city)
        city_id = city.id

    error = await update_city_settings(
        city_id=city_id,
        name="Екатеринбург",
        tz="Asia/Yekaterinburg",
        active=True,
        responsible_id=None,
        templates={},
        criteria="",
        experts="",
        plan_week=None,
        plan_month=None,
    )

    assert error is None

    async with async_session() as session:
        updated = await session.get(models.City, city_id)
        assert updated is not None
        assert updated.name == "Екатеринбург"
        assert updated.tz == "Asia/Yekaterinburg"
        assert updated.active is True


@pytest.mark.asyncio
async def test_update_template_returns_false_on_duplicate_key():
    async with async_session() as session:
        city = models.City(name="Template City", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)

        original = models.Template(city_id=city.id, key="greeting", content="Hello")
        conflicting = models.Template(city_id=city.id, key="farewell", content="Bye")
        session.add_all([original, conflicting])
        await session.commit()
        await session.refresh(original)
        await session.refresh(conflicting)

        original_id = original.id
        conflicting_key = conflicting.key
        city_id = city.id

    result = await update_template(
        original_id,
        key=conflicting_key,
        text="Updated",
        city_id=city_id,
    )

    assert result is False

    async with async_session() as session:
        persisted = await session.get(models.Template, original_id)
        assert persisted is not None
        assert persisted.key == "greeting"
        assert persisted.content == "Hello"
