from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from backend.apps.admin_ui.services.candidates import (
    delete_all_candidates,
    get_candidate_detail,
    list_candidates,
    api_candidate_detail_payload,
    update_candidate_status,
    upsert_candidate,
)
from backend.core.db import async_session
from backend.domain.candidates import (
    models as candidate_models,
    services as candidate_services,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.models import City, Recruiter, Slot, SlotStatus


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
async def test_api_candidate_detail_payload_extracts_hh_profile_url_from_answers():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=999101,
        fio="HH Link Candidate",
        city="Екатеринбург",
    )

    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=5,
        final_score=5.0,
        rating="TEST1",
        total_time=120,
        question_data=[
            {
                "question_index": 1,
                "question_text": "Ссылка на HH",
                "correct_answer": None,
                "user_answer": "Вот мой профиль: https://hh.ru/resume/abcdef12345",
                "attempts_count": 1,
                "time_spent": 10,
                "is_correct": True,
                "overtime": False,
            }
        ],
    )

    payload = await api_candidate_detail_payload(candidate.id)
    assert payload is not None
    assert payload.get("hh_profile_url") == "https://hh.ru/resume/abcdef12345"


@pytest.mark.asyncio
async def test_update_candidate_status_changes_slot_and_outcome():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777001,
        fio="Status Candidate",
        city="Пермь",
    )

    async with async_session() as session:
        recruiter = Recruiter(
            name="Status Recruiter", tz="Europe/Moscow", telemost_url=None, active=True
        )
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

    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate.id, "assigned"
    )
    assert ok is True
    assert stored_status == "assigned"
    assert dispatch is None

    async with async_session() as session:
        refreshed = await session.scalar(
            select(Slot).where(Slot.candidate_tg_id == candidate.telegram_id)
        )
        assert refreshed is not None
        assert refreshed.status == SlotStatus.BOOKED

    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate.id, "accepted"
    )
    assert ok is True
    assert stored_status == "accepted"
    async with async_session() as session:
        refreshed = await session.scalar(
            select(Slot).where(Slot.candidate_tg_id == candidate.telegram_id)
        )
        assert refreshed is not None
        assert refreshed.interview_outcome == "success"


@pytest.mark.asyncio
async def test_list_candidates_pipeline_filters_renders_correct_stage():
    interview_candidate = await candidate_services.create_or_update_user(
        telegram_id=900001,
        fio="Interview Candidate",
        city="Москва",
    )
    intro_candidate = await candidate_services.create_or_update_user(
        telegram_id=900002,
        fio="Intro Candidate",
        city="Санкт-Петербург",
    )

    async with async_session() as session:
        city = City(name="Фантомный город", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(
            name="Pipeline Recruiter", tz="Europe/Moscow", active=True
        )
        session.add_all([city, recruiter])
        await session.flush()
        interview_user = await session.get(
            candidate_models.User, interview_candidate.id
        )
        intro_user = await session.get(candidate_models.User, intro_candidate.id)
        interview_user.candidate_status = CandidateStatus.INTERVIEW_SCHEDULED
        intro_user.candidate_status = CandidateStatus.INTRO_DAY_SCHEDULED
        session.add(
            Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
                status=SlotStatus.BOOKED,
                candidate_tg_id=interview_candidate.telegram_id,
                candidate_fio=interview_candidate.fio,
                candidate_tz="Europe/Moscow",
            )
        )
        session.add(
            Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=datetime.now(timezone.utc) + timedelta(days=1),
                status=SlotStatus.BOOKED,
                purpose="intro_day",
                candidate_tg_id=intro_candidate.telegram_id,
                candidate_fio=intro_candidate.fio,
                candidate_tz="Europe/Moscow",
            )
        )
        await session.commit()

    interview_payload = await list_candidates(
        page=1,
        per_page=20,
        search=None,
        city=None,
        is_active=None,
        rating=None,
        has_tests=None,
        has_messages=None,
        stage=None,
        statuses=None,
        recruiter_id=None,
        city_ids=None,
        date_from=None,
        date_to=None,
        test1_status=None,
        test2_status=None,
        sort=None,
        sort_dir=None,
        calendar_mode=None,
        pipeline="interview",
    )
    assert interview_payload["total"] == 1
    assert (
        interview_payload["summary"]["raw_status_totals"].get("interview_scheduled")
        == 1
    )
    assert (
        interview_payload["summary"]["raw_status_totals"].get("intro_day_scheduled", 0)
        == 0
    )
    assert interview_payload["summary"]["funnel"]
    assert interview_payload["summary"]["funnel"][0]["statuses"]

    intro_payload = await list_candidates(
        page=1,
        per_page=20,
        search=None,
        city=None,
        is_active=None,
        rating=None,
        has_tests=None,
        has_messages=None,
        stage=None,
        statuses=None,
        recruiter_id=None,
        city_ids=None,
        date_from=None,
        date_to=None,
        test1_status=None,
        test2_status=None,
        sort=None,
        sort_dir=None,
        calendar_mode=None,
        pipeline="intro_day",
    )
    assert intro_payload["total"] == 1
    assert intro_payload["summary"]["raw_status_totals"].get("intro_day_scheduled") == 1
    assert (
        intro_payload["summary"]["raw_status_totals"].get("interview_scheduled", 0) == 0
    )
    intro_rows = intro_payload["views"]["table"]["rows"]
    assert intro_rows
    assert intro_rows[0]["intro_day"] is not None
    assert intro_rows[0]["intro_day"]["slot"].purpose == "intro_day"


@pytest.mark.asyncio
async def test_update_candidate_status_assigned_sends_notification(monkeypatch):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=777010,
        fio="Notifier Candidate",
        city="Казань",
    )

    async with async_session() as session:
        recruiter = Recruiter(name="Notify Recruiter", tz="Europe/Moscow", active=True)
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
        await session.refresh(slot)

    calls = {}

    async def fake_approve(slot_id: int, *, force_notify: bool = False):
        calls["slot_id"] = slot_id
        calls["force_notify"] = force_notify
        return SimpleNamespace(status="approved", message="ok", slot=None)

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.candidates.approve_slot_and_notify",
        fake_approve,
    )

    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate.id, "assigned"
    )
    assert ok is True
    assert stored_status == "assigned"
    assert dispatch is None
    assert calls.get("slot_id") is not None
    assert calls.get("force_notify") is True


@pytest.mark.asyncio
async def test_delete_all_candidates_resets_slots():
    candidate = await upsert_candidate(
        telegram_id=50123,
        fio="Bulk Remove Candidate",
        city="Москва",
        is_active=True,
    )

    async with async_session() as session:
        city = City(name="Delete City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Delete Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            candidate_city_id=city.id,
            start_utc=datetime.now(timezone.utc) + timedelta(hours=3),
            duration_min=60,
            status=SlotStatus.BOOKED,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()
        slot_id = slot.id

    deleted = await delete_all_candidates()
    assert deleted >= 1

    async with async_session() as session:
        remaining = await session.scalar(select(func.count(candidate_models.User.id)))
        assert remaining == 0
        slot = await session.get(Slot, slot_id)
    assert slot is not None
    assert slot.status == SlotStatus.FREE
    assert slot.candidate_tg_id is None


@pytest.mark.asyncio
async def test_update_candidate_status_declined_without_slot():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=88123,
        fio="No Slot Candidate",
        city="Москва",
    )

    ok, message, stored_status, dispatch = await update_candidate_status(
        candidate.id, "interview_declined"
    )
    assert ok is True
    assert stored_status == "interview_declined"
    assert dispatch is not None
    assert dispatch.status == "sent_rejection"

    async with async_session() as session:
        refreshed = await session.get(candidate_models.User, candidate.id)
        assert refreshed.candidate_status == CandidateStatus.INTERVIEW_DECLINED
