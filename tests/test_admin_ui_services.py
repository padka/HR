from datetime import date

import pytest

from backend.apps.admin_ui import services as ui_services
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_dashboard_and_slot_listing():
    async with async_session() as session:
        recruiter = models.Recruiter(name="UI", tz="Europe/Moscow", active=True)
        city = models.City(name="UI City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

    created = await ui_services.create_slot(recruiter_id=recruiter.id, date=str(date.today()), time="10:00")
    assert created is True

    counts = await ui_services.dashboard_counts()
    assert counts["recruiters"] == 1
    assert counts["cities"] == 1
    assert counts["slots_total"] == 1

    listing = await ui_services.list_slots(
        recruiter_id=None,
        status=None,
        page=1,
        per_page=10,
    )
    assert listing["total"] == 1
    assert listing["items"][0].recruiter_id == recruiter.id


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

    error = await ui_services.assign_city_owner(city_id=city.id, recruiter_id=recruiter.id)
    assert error is None

    owners_payload = await ui_services.api_city_owners_payload()
    assert owners_payload["ok"]
    assert owners_payload["owners"][city.id] == recruiter.id

    template_payload = await ui_services.api_templates_payload(city_id=None, key="invite")
    assert isinstance(template_payload, list)
    texts = {item["text"] for item in template_payload}
    assert "global" in texts
