from datetime import date

import pytest

from backend.apps.admin_ui.services.dashboard import dashboard_counts
from backend.apps.admin_ui.services.slots import create_slot, list_slots
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

    created = await create_slot(recruiter_id=recruiter.id, date=str(date.today()), time="10:00")
    assert created is True

    counts = await dashboard_counts()
    assert counts["recruiters"] == 1
    assert counts["cities"] == 1
    assert counts["slots_total"] == 1

    listing = await list_slots(
        recruiter_id=None,
        status=None,
        page=1,
        per_page=10,
    )
    assert listing["total"] == 1
    assert listing["items"][0].recruiter_id == recruiter.id
