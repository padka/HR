from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.models import User
from backend.domain.models import Slot, SlotStatus, Recruiter


@pytest.mark.asyncio
async def test_intro_day_button_visible_after_test2_completion():
    # Create candidate with TEST2_COMPLETED
    async with async_session() as session:
        user = User(
            telegram_id=999001,
            fio="Test Intro Day",
            city="Москва",
            candidate_status=CandidateStatus.TEST2_COMPLETED,
            is_active=True,
        )
        session.add(user)

        # Create recruiter for the slot
        recruiter = Recruiter(name="Test Recruiter", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.commit()
        await session.refresh(user)
        await session.refresh(recruiter)

        # Create an intro_day slot to ensure availability
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=datetime.now(timezone.utc),
            status=SlotStatus.FREE,
            candidate_tg_id=None,
        )
        session.add(slot)
        await session.commit()

    from backend.core import settings as settings_module
    settings_module.get_settings.cache_clear()
    app = create_app()
    async with AsyncClient(
        app=app,
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        response = await client.get(f"/candidates/{user.id}")
        assert response.status_code == 200
        html = response.text
        assert "Назначить ознакомительный день" in html


@pytest.mark.asyncio
async def test_intro_day_button_hidden_when_already_has_intro_slot():
    async with async_session() as session:
        user = User(
            telegram_id=999002,
            fio="Test Intro Day 2",
            city="Москва",
            candidate_status=CandidateStatus.TEST2_COMPLETED,
            is_active=True,
        )
        session.add(user)

        # Create recruiter for the slot
        recruiter = Recruiter(name="Test Recruiter 2", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.commit()
        await session.refresh(user)
        await session.refresh(recruiter)

        # Existing intro_day slot for this candidate
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=datetime.now(timezone.utc),
            status=SlotStatus.BOOKED,
            candidate_tg_id=user.telegram_id,
        )
        session.add(slot)
        await session.commit()

    from backend.core import settings as settings_module
    settings_module.get_settings.cache_clear()
    app = create_app()
    async with AsyncClient(
        app=app,
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        response = await client.get(f"/candidates/{user.id}")
        assert response.status_code == 200
        html = response.text
        assert "Назначить ознакомительный день" not in html
