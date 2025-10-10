from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import (
    AutoMessage,
    CandidateTestOutcome,
    CandidateTestOutcomeDelivery,
    Notification,
    QuestionAnswer,
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
async def test_candidate_test_outcome_persistence_and_delivery():
    user = await candidate_services.create_or_update_user(
        telegram_id=3030, fio="Outcome Tester", city="Пермь"
    )
    attempt_at = datetime.now(timezone.utc)

    persisted = await candidate_services.record_candidate_test_outcome(
        user_id=user.id,
        test_id="TEST2",
        status="passed",
        rating="A",
        score=4.5,
        correct_answers=5,
        total_questions=6,
        attempt_at=attempt_at,
        artifact_path="test_results/sample.json",
        artifact_name="sample.json",
        artifact_mime="application/json",
        artifact_size=128,
        payload={"foo": "bar"},
    )

    assert persisted.created is True
    outcome = persisted.outcome
    assert outcome.test_id == "TEST2"

    # Duplicate webhook should update, not create new entry
    duplicated = await candidate_services.record_candidate_test_outcome(
        user_id=user.id,
        test_id="TEST2",
        status="passed",
        rating="A",
        score=4.5,
        correct_answers=5,
        total_questions=6,
        attempt_at=attempt_at,
        artifact_path="test_results/sample.json",
        artifact_name="sample.json",
        artifact_mime="application/json",
        artifact_size=128,
        payload={"foo": "bar"},
    )

    assert duplicated.created is False

    delivered_before = await candidate_services.was_test_outcome_delivered(
        outcome.id, chat_id=9999
    )
    assert delivered_before is False

    await candidate_services.mark_test_outcome_delivered(
        outcome.id, chat_id=9999, message_id=42
    )

    delivered_after = await candidate_services.was_test_outcome_delivered(
        outcome.id, chat_id=9999
    )
    assert delivered_after is True

    # A repeated mark with a new message id should update the record instead of duplicating
    await candidate_services.mark_test_outcome_delivered(
        outcome.id, chat_id=9999, message_id=77
    )

    async with async_session() as session:
        stored_outcomes = (
            await session.execute(
                select(CandidateTestOutcome).where(
                    CandidateTestOutcome.user_id == user.id
                )
            )
        ).scalars().all()
        assert len(stored_outcomes) == 1

        deliveries = (
            await session.execute(
                select(CandidateTestOutcomeDelivery).where(
                    CandidateTestOutcomeDelivery.outcome_id == outcome.id
                )
            )
        ).scalars().all()
        assert len(deliveries) == 1
        assert deliveries[0].message_id == 77
