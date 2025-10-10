from datetime import datetime, timezone

import pytest

from backend.apps.admin_ui.services.candidates import (
    get_candidate_detail,
    list_candidates,
    upsert_candidate,
)
from backend.domain.candidates import services as candidate_services


@pytest.mark.asyncio
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

    attempt_at = datetime.now(timezone.utc)
    await candidate_services.record_candidate_test_outcome(
        user_id=user.id,
        test_id="TEST2",
        status="passed",
        rating="A",
        score=8.5,
        correct_answers=8,
        total_questions=10,
        attempt_at=attempt_at,
        artifact_path="test_results/sample.json",
        artifact_name="sample.json",
        artifact_mime="application/json",
        artifact_size=256,
        payload={"sample": True},
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
    assert detail["test_outcomes"]
    assert "slots" in detail
    assert "timeline" in detail
