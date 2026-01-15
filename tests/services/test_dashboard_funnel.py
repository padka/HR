from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from backend.apps.admin_ui.services.dashboard import (
    get_bot_funnel_stats,
    get_funnel_step_candidates,
)
from backend.core.db import async_session
from backend.domain.analytics import FunnelEvent
from backend.domain.candidates.models import User


async def _insert_event(
    *,
    session,
    event_name: str,
    user_id: int,
    candidate_id: int,
    created_at: datetime,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO analytics_events (event_name, user_id, candidate_id, created_at)
            VALUES (:event_name, :user_id, :candidate_id, :created_at)
            """
        ),
        {
            "event_name": event_name,
            "user_id": user_id,
            "candidate_id": candidate_id,
            "created_at": created_at,
        },
    )


@pytest.mark.asyncio
async def test_bot_funnel_stats_counts_and_dropoffs():
    base_time = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    async with async_session() as session:
        await session.execute(text("DELETE FROM analytics_events"))
        user1 = User(
            telegram_id=1001,
            fio="User One",
            city="Moscow",
            last_activity=base_time,
        )
        user2 = User(
            telegram_id=1002,
            fio="User Two",
            city="Moscow",
            last_activity=base_time,
        )
        session.add_all([user1, user2])
        await session.commit()
        await session.refresh(user1)
        await session.refresh(user2)

        await _insert_event(
            session=session,
            event_name=FunnelEvent.BOT_ENTERED.value,
            user_id=user1.telegram_id,
            candidate_id=user1.id,
            created_at=base_time,
        )
        await _insert_event(
            session=session,
            event_name=FunnelEvent.TEST1_STARTED.value,
            user_id=user1.telegram_id,
            candidate_id=user1.id,
            created_at=base_time + timedelta(hours=1),
        )
        await _insert_event(
            session=session,
            event_name=FunnelEvent.TEST1_COMPLETED.value,
            user_id=user1.telegram_id,
            candidate_id=user1.id,
            created_at=base_time + timedelta(hours=2),
        )
        await _insert_event(
            session=session,
            event_name=FunnelEvent.BOT_ENTERED.value,
            user_id=user2.telegram_id,
            candidate_id=user2.id,
            created_at=base_time + timedelta(minutes=30),
        )
        await _insert_event(
            session=session,
            event_name=FunnelEvent.TEST1_STARTED.value,
            user_id=user2.telegram_id,
            candidate_id=user2.id,
            created_at=base_time + timedelta(hours=1),
        )
        await session.commit()

    stats = await get_bot_funnel_stats(
        date_from=base_time - timedelta(hours=1),
        date_to=base_time + timedelta(hours=5),
    )
    steps = {step["key"]: step for step in stats["steps"]}

    assert steps["entered"]["count"] == 2
    assert steps["test1_started"]["count"] == 2
    assert steps["test1_completed"]["count"] == 1
    assert steps["test1_completed"]["conversion_from_prev"] == 50.0
    assert stats["dropoffs"]["no_test1"] == 0
    assert stats["dropoffs"]["test1_timeout"] == 1
    assert steps["test1_completed"]["avg_time_to_step_sec"] == pytest.approx(3600.0, rel=1e-2)


@pytest.mark.asyncio
async def test_funnel_step_candidates_drilldown():
    base_time = datetime(2025, 2, 1, 10, 0, tzinfo=timezone.utc)
    async with async_session() as session:
        await session.execute(text("DELETE FROM analytics_events"))
        user = User(
            telegram_id=2001,
            fio="Drop User",
            city="Moscow",
            last_activity=base_time,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        await _insert_event(
            session=session,
            event_name=FunnelEvent.BOT_ENTERED.value,
            user_id=user.telegram_id,
            candidate_id=user.id,
            created_at=base_time,
        )
        await _insert_event(
            session=session,
            event_name=FunnelEvent.TEST1_STARTED.value,
            user_id=user.telegram_id,
            candidate_id=user.id,
            created_at=base_time + timedelta(hours=1),
        )
        await session.commit()

    items = await get_funnel_step_candidates(
        step_key="test1_started",
        date_from=base_time - timedelta(hours=1),
        date_to=base_time + timedelta(hours=5),
    )
    assert any(item["id"] == user.id for item in items)

    drop_items = await get_funnel_step_candidates(
        step_key="test1_timeout",
        date_from=base_time - timedelta(hours=1),
        date_to=base_time + timedelta(hours=5),
    )
    assert any(item["id"] == user.id for item in drop_items)
