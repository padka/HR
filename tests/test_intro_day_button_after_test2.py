from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport

from backend.apps.admin_ui.app import create_app
from backend.apps.admin_ui.services.candidates import get_candidate_detail, update_candidate_status
from backend.core.db import async_session
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.models import TestResult, User
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
        transport=ASGITransport(app=app),
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
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        response = await client.get(f"/candidates/{user.id}")
        assert response.status_code == 200
        html = response.text
        assert "Назначить ознакомительный день" not in html


@pytest.mark.asyncio
async def test_intro_day_slot_freed_after_rejection():
    """When кандидат не прошел Тест 2, связанные слоты ОД освобождаются."""
    async with async_session() as session:
        user = User(
            telegram_id=999003,
            fio="Declined After Test2",
            city="Москва",
            candidate_status=CandidateStatus.TEST2_COMPLETED,
            is_active=True,
        )
        recruiter = Recruiter(name="Intro Rec 3", tz="Europe/Moscow", active=True)
        session.add_all([user, recruiter])
        await session.commit()
        await session.refresh(user)
        await session.refresh(recruiter)

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
            status=SlotStatus.BOOKED,
            candidate_tg_id=user.telegram_id,
            candidate_fio=user.fio,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        slot_id = slot.id

    ok, _msg, stored_status, _ = await update_candidate_status(user.id, "test2_failed")
    assert ok is True
    assert stored_status == "test2_failed"

    async with async_session() as session:
        updated_slot = await session.get(Slot, slot_id)
        updated_user = await session.get(User, user.id)

        assert updated_user.candidate_status == CandidateStatus.TEST2_FAILED
        assert updated_slot.status == SlotStatus.FREE
        assert updated_slot.candidate_tg_id is None
        assert updated_slot.candidate_id is None
        assert (updated_slot.purpose or "").lower() == "intro_day"


@pytest.mark.asyncio
async def test_actions_not_downgraded_after_intro_day_scheduled():
    """Действия после назначения ОД не должны откатываться к этапу теста."""
    async with async_session() as session:
        user = User(
            telegram_id=999004,
            fio="Intro Day Scheduled",
            city="Москва",
            candidate_status=CandidateStatus.INTRO_DAY_SCHEDULED,
            is_active=True,
        )
        recruiter = Recruiter(name="Intro Rec 4", tz="Europe/Moscow", active=True)
        session.add_all([user, recruiter])
        await session.commit()
        await session.refresh(user)
        await session.refresh(recruiter)

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=datetime.now(timezone.utc) + timedelta(hours=3),
            status=SlotStatus.BOOKED,
            candidate_tg_id=user.telegram_id,
            candidate_fio=user.fio,
        )
        session.add(slot)
        # Добавим пройденный тест 2, чтобы не было даунгрейда действий
        result = TestResult(
            user_id=user.id,
            raw_score=8,
            final_score=8.0,
            rating="TEST2",
            total_time=120,
        )
        session.add(result)
        await session.commit()

    detail = await get_candidate_detail(user.id)
    actions = detail["candidate_actions"]
    action_keys = {a.key for a in actions}

    assert detail["candidate_status_slug"] == CandidateStatus.INTRO_DAY_SCHEDULED.value
    assert "reschedule_intro_day" in action_keys
    assert "reject" not in action_keys  # Не показываем отказ с откатом на test2_failed
