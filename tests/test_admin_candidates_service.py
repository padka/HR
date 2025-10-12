from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.apps.admin_ui.services.candidates import (
    get_candidate_detail,
    list_candidates,
    save_interview_feedback,
    schedule_intro_day_message,
    upsert_candidate,
)
from backend.core.db import async_session
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import AutoMessage
from backend.domain.models import Recruiter, Slot


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_list_candidates_and_detail():
    user = await upsert_candidate(
        telegram_id=4321,
        fio="Тестовый Кандидат",
        city="Москва",
        is_active=True,
    )

    await candidate_services.save_test_result(
        user_id=user.id,
        raw_score=10,
        final_score=8.5,
        rating="A",
        total_time=420,
        question_data=[
            {
                "question_index": 1,
                "question_text": "Q1",
                "correct_answer": "A",
                "user_answer": "A",
                "attempts_count": 1,
                "time_spent": 30,
                "is_correct": True,
                "overtime": False,
            }
        ],
    )

    await candidate_services.create_auto_message(
        message_text="Напоминание",
        send_time="15:00",
        target_chat_id=user.telegram_id,
    )

    payload = await list_candidates(
        page=1,
        per_page=10,
        search="Тестовый",
        city="Москва",
        is_active=True,
        rating="A",
        has_tests=True,
        has_messages=True,
    )

    assert payload["total"] == 1
    row = payload["items"][0]
    assert row.tests_total == 1
    assert row.messages_total == 1
    assert row.latest_result is not None
    assert row.stage
    assert "analytics" in payload
    assert payload["analytics"]["total"] >= 1

    detail = await get_candidate_detail(user.id)
    assert detail is not None
    assert detail["stats"]["tests_total"] == 1
    assert detail["messages"]
    assert detail["tests"]
    assert "slots" in detail
    assert "timeline" in detail
    assert detail["interview_script"]
    assert "intro_message_template" in detail
    first_test = detail["tests"][0]
    assert detail["answers_map"][first_test.id]["questions_total"] == 1


@pytest.mark.anyio
async def test_save_feedback_and_schedule_intro_day():
    user = await upsert_candidate(
        telegram_id=9991,
        fio="Марина Петрова",
        city="Казань",
        is_active=True,
    )

    async with async_session() as session:
        recruiter = Recruiter(name="Тестовый рекрутёр", tg_chat_id=None, tz="Europe/Moscow", telemost_url=None, active=True)
        session.add(recruiter)
        await session.flush()
        slot = Slot(
            recruiter_id=recruiter.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
            duration_min=30,
            candidate_tg_id=user.telegram_id,
            candidate_fio=user.fio,
            candidate_tz="Europe/Moscow",
            status="booked",
        )
        session.add(slot)
        await session.commit()
        slot_id = slot.id

    ok, message = await save_interview_feedback(
        slot_id,
        ["greeting", "experience"],
        "Очень уверенный кандидат",
        candidate_id=user.id,
    )

    assert ok is True
    assert "сохранены" in (message or "")

    async with async_session() as session:
        stored_slot = await session.get(Slot, slot_id)
        assert stored_slot is not None
        assert stored_slot.interview_feedback is not None
        checklist = stored_slot.interview_feedback.get("checklist", {})
        assert checklist.get("greeting") is True
        assert checklist.get("experience") is True
        assert stored_slot.interview_feedback.get("notes") == "Очень уверенный кандидат"

    ok_msg, msg_text = await schedule_intro_day_message(
        user.id,
        date_value="2030-01-02",
        time_value="10:30",
        message_text="",
    )

    assert ok_msg is True
    assert "запланировано" in (msg_text or "")

    async with async_session() as session:
        messages = (
            await session.execute(
                select(AutoMessage).where(AutoMessage.target_chat_id == user.telegram_id)
            )
        ).scalars().all()
        assert any(message.send_time == "2030-01-02 10:30" for message in messages)
