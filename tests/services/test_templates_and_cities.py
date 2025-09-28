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
