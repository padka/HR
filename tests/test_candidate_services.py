import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import (
    AutoMessage,
    Notification,
    QuestionAnswer,
    SurveyResponse,
    TestResult,
    User,
)


@pytest.mark.asyncio
async def test_create_or_update_user_and_lookup():
    created = await candidate_services.create_or_update_user(telegram_id=1001, fio="Иван Иванов", city="Москва")
    assert isinstance(created, User)
    assert created.telegram_id == 1001
    assert created.city == "Москва"

    updated = await candidate_services.create_or_update_user(telegram_id=1001, fio="Иван И.", city="Санкт-Петербург")
    assert updated.id == created.id
    assert updated.fio == "Иван И."
    assert updated.city == "Санкт-Петербург"

    fetched = await candidate_services.get_user_by_telegram_id(1001)
    assert fetched is not None
    assert fetched.id == created.id

    active_users = await candidate_services.get_all_active_users()
    assert len(active_users) == 1
    assert active_users[0].telegram_id == 1001


@pytest.mark.asyncio
async def test_save_test_result_and_statistics():
    user = await candidate_services.create_or_update_user(telegram_id=2002, fio="Анна Петрова", city="Новосибирск")

    result = await candidate_services.save_test_result(
        user_id=user.id,
        raw_score=7,
        final_score=6.5,
        rating="A",
        total_time=320,
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
            },
            {
                "question_index": 2,
                "question_text": "Q2",
                "correct_answer": "B",
                "user_answer": "C",
                "attempts_count": 2,
                "time_spent": 45,
                "is_correct": False,
                "overtime": True,
            },
        ],
    )

    assert isinstance(result, TestResult)

    async with async_session() as session:
        stored = await session.get(TestResult, result.id)
        assert stored is not None
        answers = (await session.execute(
            select(QuestionAnswer).where(QuestionAnswer.test_result_id == result.id)
        )).scalars().all()
        assert len(answers) == 2
        assert any(a.is_correct for a in answers)
        assert any(a.overtime for a in answers)

    stats = await candidate_services.get_test_statistics()
    assert stats["total_tests"] == 1
    assert stats["completed_tests"] == 1
    assert stats["average_score"] == 6.5
    assert stats["success_rate"] == 100.0


@pytest.mark.asyncio
async def test_auto_messages_and_notifications():
    created = await candidate_services.create_auto_message(
        message_text="Напоминание",
        send_time="09:00",
        target_chat_id=555,
    )
    assert isinstance(created, AutoMessage)

    active = await candidate_services.get_active_auto_messages()
    assert len(active) == 1
    assert active[0].message_text == "Напоминание"

    notification = await candidate_services.create_notification(
        admin_chat_id=777,
        notification_type="alert",
        message_text="Проверить заявки",
    )
    assert isinstance(notification, Notification)
    assert notification.is_sent is False

    await candidate_services.mark_notification_sent(notification.id)

    async with async_session() as session:
        stored = await session.get(Notification, notification.id)
        assert stored is not None
        assert stored.is_sent is True
        assert isinstance(stored.sent_at, datetime)


@pytest.mark.asyncio
async def test_save_and_load_survey_response():
    user = await candidate_services.create_or_update_user(
        telegram_id=3003,
        fio="Сергей Смирнов",
        city="Казань",
    )

    payload = {
        "meta": {
            "telegram_id": user.telegram_id,
            "fio": user.fio,
            "city": user.city,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "questions": [
            {"id": "fio", "prompt": "ФИО", "answer": user.fio},
            {"id": "city", "prompt": "Город", "answer": user.city},
        ],
        "summary_text": "summary",
    }

    saved = await candidate_services.save_survey_response(user.id, payload)
    assert isinstance(saved, SurveyResponse)

    loaded = await candidate_services.load_survey_summary(user.id)
    assert loaded is not None

    restored = json.loads(loaded.answers_json)
    assert restored["meta"]["fio"] == user.fio
    assert restored["questions"][0]["prompt"] == "ФИО"
