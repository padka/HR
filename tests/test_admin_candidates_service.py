from datetime import datetime, timedelta, timezone

import pytest

from sqlalchemy import select

from backend.apps.admin_ui.services.candidates import (
    get_candidate_detail,
    list_candidates,
    upsert_candidate,
    update_candidate_status,
)
from backend.domain.candidates import services as candidate_services
from backend.core.db import async_session
from backend.domain.models import Recruiter, Slot, SlotStatus


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
    assert "views" in payload
    assert isinstance(payload["views"].get("candidates"), list)
    assert payload["views"]["candidates"]
    kanban_view = payload["views"].get("kanban", {})
    assert isinstance(kanban_view.get("columns"), list)
    assert kanban_view["columns"]
    assert payload["filters"].get("sort") == "event"

    detail = await get_candidate_detail(user.id)
    assert detail is not None
    assert detail["stats"]["tests_total"] == 1
    assert detail["messages"]
    assert detail["tests"]
    assert "slots" in detail
    assert "timeline" in detail


@pytest.mark.asyncio
async def test_candidate_detail_includes_test_sections_and_telemost():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=999001,
        fio="Test Sections",
        city="Новосибирск",
    )

    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=5,
        final_score=5.0,
        rating="TEST1",
        total_time=300,
        question_data=[
            {
                "question_index": idx + 1,
                "question_text": f"T1 Question {idx + 1}",
                "correct_answer": None,
                "user_answer": f"Answer {idx + 1}",
                "attempts_count": 1,
                "time_spent": 20,
                "is_correct": True,
                "overtime": False,
            }
            for idx in range(5)
        ],
    )

    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=1,
        final_score=0.5,
        rating="TEST2",
        total_time=180,
        question_data=[
            {
                "question_index": 1,
                "question_text": "T2 Question 1",
                "correct_answer": "Correct A",
                "user_answer": "Correct A",
                "attempts_count": 1,
                "time_spent": 30,
                "is_correct": True,
                "overtime": False,
            },
            {
                "question_index": 2,
                "question_text": "T2 Question 2",
                "correct_answer": "Correct B",
                "user_answer": "Wrong",
                "attempts_count": 2,
                "time_spent": 45,
                "is_correct": False,
                "overtime": True,
            },
        ],
    )

    telemost_url = "https://telemost.example/room"
    start = datetime.now(timezone.utc) + timedelta(days=1)
    async with async_session() as session:
        recruiter = Recruiter(
            name="Sections Recruiter",
            tz="Europe/Moscow",
            telemost_url=telemost_url,
            active=True,
        )
        session.add(recruiter)
        await session.flush()

        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            candidate_city_id=None,
            start_utc=start,
            duration_min=45,
            status=SlotStatus.BOOKED,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Asia/Novosibirsk",
        )
        session.add(slot)
        await session.commit()

    detail = await get_candidate_detail(candidate.id)
    assert detail is not None

    sections = {section["key"]: section for section in detail["test_sections"]}
    assert sections["test1"]["status"] == "passed"
    assert sections["test1"]["details"]["questions"]
    assert sections["test2"]["status"] == "failed"
    assert len(sections["test2"]["details"]["questions"]) == 2

    assert detail["telemost_url"] == telemost_url
    assert detail["telemost_source"] == "upcoming"


@pytest.mark.asyncio
async def test_update_candidate_status_changes_slot_and_outcome():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777001,
        fio="Status Candidate",
        city="Пермь",
    )

    async with async_session() as session:
        recruiter = Recruiter(name="Status Recruiter", tz="Europe/Moscow", telemost_url=None, active=True)
        session.add(recruiter)
        await session.flush()
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=None,
            candidate_city_id=None,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=SlotStatus.PENDING,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()

    ok, message, stored_status, dispatch = await update_candidate_status(candidate.id, "assigned")
    assert ok is True
    assert stored_status == "assigned"
    assert dispatch is None

    async with async_session() as session:
        refreshed = await session.scalar(
            select(Slot).where(Slot.candidate_tg_id == candidate.telegram_id)
        )
        assert refreshed is not None
        assert refreshed.status == SlotStatus.BOOKED

    ok, message, stored_status, dispatch = await update_candidate_status(candidate.id, "accepted")
    assert ok is True
    assert stored_status == "accepted"
    async with async_session() as session:
        refreshed = await session.scalar(
            select(Slot).where(Slot.candidate_tg_id == candidate.telegram_id)
        )
        assert refreshed is not None
        assert refreshed.interview_outcome == "success"
