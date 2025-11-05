"""Test intro day scheduling and notification flow"""
from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from backend.apps.admin_ui.services.candidates import get_candidate_detail
from backend.domain.candidates import services as candidate_services
from backend.domain.models import Recruiter, Slot, SlotStatus, City
from backend.core.db import async_session


@pytest.mark.asyncio
async def test_intro_day_status_detection():
    """Test that candidate shows needs_intro_day after passing TEST2 but before scheduling"""
    # Create candidate
    candidate = await candidate_services.create_or_update_user(
        telegram_id=888001,
        fio="Иван Тестов",
        city="Сочи",
    )

    # Initially should NOT need intro day (no TEST2 passed)
    detail = await get_candidate_detail(candidate.id)
    assert detail is not None
    assert detail.get("needs_intro_day") == False, "Should not need intro day without TEST2"

    # Pass TEST2 - need rating="TEST2" and >= 75% correct (0.75 threshold)
    # Create 10 questions with 8 correct (80% pass rate)
    question_data = [
        {
            "question_index": i,
            "question_text": f"Test2 Q{i}",
            "correct_answer": "A",
            "user_answer": "A" if i <= 8 else "B",  # 8 correct, 2 wrong
            "attempts_count": 1,
            "time_spent": 30,
            "is_correct": i <= 8,
            "overtime": False,
        }
        for i in range(1, 11)
    ]

    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=8,  # 8 correct out of 10
        final_score=8.0,
        rating="TEST2",  # This marks it as TEST2
        total_time=300,
        question_data=question_data,
    )

    # Now should need intro day
    detail2 = await get_candidate_detail(candidate.id)
    assert detail2.get("needs_intro_day") == True, "Should need intro day after passing TEST2"


@pytest.mark.asyncio
async def test_intro_day_slot_creation_and_status_update():
    """Test creating intro_day slot and verifying status updates"""
    # Create candidate who passed TEST2
    candidate = await candidate_services.create_or_update_user(
        telegram_id=888002,
        fio="Петр Тестовский",
        city="Москва",
    )

    # Pass TEST2
    question_data = [
        {
            "question_index": i,
            "question_text": f"Test2 Q{i}",
            "correct_answer": "A",
            "user_answer": "A" if i <= 8 else "B",
            "attempts_count": 1,
            "time_spent": 30,
            "is_correct": i <= 8,
            "overtime": False,
        }
        for i in range(1, 11)
    ]

    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=8,
        final_score=8.0,
        rating="TEST2",
        total_time=300,
        question_data=question_data,
    )

    # Verify needs intro day
    detail = await get_candidate_detail(candidate.id)
    assert detail.get("needs_intro_day") == True

    # Create city and recruiter
    async with async_session() as session:
        city = City(name="Москва")
        session.add(city)
        await session.flush()

        recruiter = Recruiter(
            name="Виталий Рекрутер",
            tg_chat_id=777001,
            tz="Europe/Moscow",
        )
        session.add(recruiter)
        await session.flush()

        # Create intro_day slot
        start_time = datetime.utcnow() + timedelta(days=1)
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=start_time,
            status=SlotStatus.BOOKED,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()

    # After creating slot, should NOT need intro day anymore
    detail2 = await get_candidate_detail(candidate.id)
    assert detail2.get("needs_intro_day") == False, "Should not need intro day after scheduling"
    assert len(detail2.get("slots", [])) == 1, "Should have one slot"
    assert detail2["slots"][0].purpose == "intro_day"


@pytest.mark.asyncio
async def test_intro_day_duplicate_prevention():
    """Test that duplicate intro_day slots are detected"""
    # Create candidate who passed TEST2
    candidate = await candidate_services.create_or_update_user(
        telegram_id=888003,
        fio="Мария Дубликатова",
        city="Сочи",
    )

    # Pass TEST2
    question_data = [
        {
            "question_index": i,
            "question_text": f"Test2 Q{i}",
            "correct_answer": "A",
            "user_answer": "A" if i <= 8 else "B",
            "attempts_count": 1,
            "time_spent": 30,
            "is_correct": i <= 8,
            "overtime": False,
        }
        for i in range(1, 11)
    ]

    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=8,
        final_score=8.0,
        rating="TEST2",
        total_time=300,
        question_data=question_data,
    )

    # Create city and recruiter
    async with async_session() as session:
        city = City(name="Сочи")
        session.add(city)
        await session.flush()

        recruiter = Recruiter(
            name="Иван Рекрутер",
            tg_chat_id=777002,
            tz="Europe/Moscow",
        )
        session.add(recruiter)
        await session.flush()

        # Create first intro_day slot
        start_time = datetime.utcnow() + timedelta(days=1)
        slot1 = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            purpose="intro_day",
            tz_name="Europe/Moscow",
            start_utc=start_time,
            status=SlotStatus.BOOKED,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot1)
        await session.commit()

        # Now check if we can detect existing slot
        existing_check = select(Slot).where(
            Slot.candidate_tg_id == candidate.telegram_id,
            Slot.recruiter_id == recruiter.id,
            Slot.purpose == "intro_day",
        )
        result = await session.execute(existing_check)
        existing_slot = result.scalar_one_or_none()

        assert existing_slot is not None, "Should find existing intro_day slot"
        assert existing_slot.id == slot1.id, "Should find the same slot we just created"
