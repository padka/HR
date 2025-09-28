import pytest

from backend.apps.admin_ui.services.cities import assign_city_owner, api_city_owners_payload
from backend.apps.admin_ui.services.templates import api_templates_payload
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_template_payloads_and_city_owner_assignment():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Owner", tz="Europe/Moscow", active=True)
        city = models.City(name="Owner City", tz="Europe/Moscow", active=True)
        template = models.Template(city_id=None, key="invite", content="global")
        session.add_all([recruiter, city, template])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        await session.refresh(template)

    error = await assign_city_owner(city_id=city.id, recruiter_id=recruiter.id)
    assert error is None

    owners_payload = await api_city_owners_payload()
    assert owners_payload["ok"]
    assert owners_payload["owners"][city.id] == recruiter.id

    template_payload = await api_templates_payload(city_id=None, key="invite")
    assert isinstance(template_payload, list)
    texts = {item["text"] for item in template_payload}
    assert "global" in texts
