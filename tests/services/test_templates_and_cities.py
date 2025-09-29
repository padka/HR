import pytest

from backend.apps.admin_ui.services.cities import (
    api_city_owners_payload,
    update_city_settings,
)
from backend.apps.admin_ui.services.templates import api_templates_payload
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
    )
    assert error is None

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
    )

    assert error is not None
    assert "Unknown template keys" in error

    async with async_session() as session:
        refreshed_city = await session.get(models.City, city.id)
        assert refreshed_city.responsible_recruiter_id is None
        await session.refresh(refreshed_city, attribute_names=["templates"])
        assert refreshed_city.templates == []
