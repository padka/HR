from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("starlette")

from backend.apps.admin_ui.services.dashboard_calendar import dashboard_calendar_snapshot
from backend.apps.bot.metrics import reset_test1_metrics
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import User


@pytest.mark.asyncio
async def test_dashboard_calendar_snapshot_links_candidates():
    await reset_test1_metrics()
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_today = now.replace(hour=10)
    start_tomorrow = start_today + timedelta(days=1)

    async with async_session() as session:
        recruiter = models.Recruiter(name="Calendar", tz="Europe/Moscow", active=True)
        city = models.City(name="Calendar City", tz="Europe/Moscow", active=True)
        candidate = User(telegram_id=123456789, fio="Кандидат Календарь", is_active=True)
        session.add_all([recruiter, city, candidate])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        await session.refresh(candidate)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
        await session.refresh(city)

        session.add_all(
            [
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=start_today,
                    status=models.SlotStatus.BOOKED,
                    candidate_tg_id=candidate.telegram_id,
                    candidate_fio=candidate.fio,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=start_tomorrow,
                    status=models.SlotStatus.PENDING,
                ),
            ]
        )
        await session.commit()

    snapshot = await dashboard_calendar_snapshot(start_today.date())
    assert snapshot["selected_date"] == start_today.date().isoformat()
    assert snapshot["events_total"] == 1
    assert snapshot["status_summary"]["BOOKED"] == 1
    assert snapshot["status_summary"]["PENDING"] >= 0
    assert any(day["is_selected"] for day in snapshot["days"])
    assert snapshot["events"], "expected events for selected date"
    event = snapshot["events"][0]
    assert event["candidate"]["profile_url"].endswith(f"/{candidate.id}")
