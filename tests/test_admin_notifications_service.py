from datetime import datetime, timedelta, timezone

import pytest

from backend.apps.admin_ui.services.notifications import notification_feed
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_notification_feed_returns_ordered_items():
    async with async_session() as session:
        recruiter = models.Recruiter(name="FeedSvc", tz="Europe/Moscow", active=True)
        city = models.City(name="FeedSvc City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=6),
            status=models.SlotStatus.BOOKED,
            candidate_tg_id=9401,
            candidate_fio="Feed Service",
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        first_log = models.NotificationLog(
            booking_id=slot.id,
            candidate_tg_id=slot.candidate_tg_id,
            type="interview_confirmed_candidate",
            payload="{}",
            delivery_status="sent",
            attempts=1,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        second_log = models.NotificationLog(
            booking_id=slot.id,
            candidate_tg_id=slot.candidate_tg_id,
            type="slot_reminder:remind_1h",
            payload="{}",
            delivery_status="failed",
            attempts=2,
            last_error="timeout",
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([first_log, second_log])
        await session.commit()
        await session.refresh(first_log)
        await session.refresh(second_log)
        first_id = first_log.id

    items = await notification_feed(after_id=None, limit=10)
    assert items, "feed should return at least one log"
    assert items[-1]["id"] == second_log.id

    filtered = await notification_feed(after_id=first_id, limit=10)
    assert filtered
    assert filtered[0]["id"] == second_log.id
    assert filtered[0]["status"] == "failed"
