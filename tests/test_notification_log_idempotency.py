import pytest
from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.models import NotificationLog
from backend.domain.repositories import add_notification_log


@pytest.mark.asyncio
async def test_add_notification_log_is_idempotent_for_same_booking():
    booking_id = 123
    log_type = "intro_day_invitation"
    candidate_tg_id = 999

    first = await add_notification_log(
        log_type,
        booking_id,
        candidate_tg_id=candidate_tg_id,
        payload="{}",
    )
    second = await add_notification_log(
        log_type,
        booking_id,
        candidate_tg_id=candidate_tg_id,
        payload="{}",
    )

    assert first is True
    assert second is False  # second insert should be no-op, not crash

    async with async_session() as session:
        rows = (
            await session.execute(
                select(NotificationLog).where(
                    NotificationLog.type == log_type,
                    NotificationLog.booking_id == booking_id,
                )
            )
        ).scalars().all()
    assert len(rows) == 1
