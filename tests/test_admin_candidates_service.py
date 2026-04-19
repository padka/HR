from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from backend.apps.admin_ui.security import Principal
from backend.apps.admin_ui.services.candidates import (
    _map_to_workflow_status,
    api_candidate_detail_payload,
    delete_all_candidates,
    get_candidate_cohort_comparison,
    get_candidate_detail,
    list_candidates,
    update_candidate_status,
    upsert_candidate,
)
from backend.apps.admin_ui.services.reschedule_intents import RescheduleIntent
from backend.core.db import async_session
from backend.domain.candidates import (
    models as candidate_models,
)
from backend.domain.candidates import (
    services as candidate_services,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.workflow import WorkflowStatus
from backend.domain.models import (
    City,
    MessageTemplate,
    Recruiter,
    Slot,
    SlotAssignment,
    SlotAssignmentStatus,
    SlotStatus,
)
from backend.domain.scheduling_repair_service import (
    repair_slot_assignment_scheduling_conflict,
)
from sqlalchemy import func, select


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
    assert payload["views"]["candidates"][0]["lifecycle_summary"]["record_state"] == "active"
    assert payload["views"]["candidates"][0]["candidate_next_action"]["worklist_bucket"] in {
        "incoming",
        "awaiting_recruiter",
        "awaiting_candidate",
    }
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
    assert detail["lifecycle_summary"]["record_state"] == "active"
    assert isinstance(detail["state_reconciliation"]["issues"], list)


@pytest.mark.asyncio
async def test_admin_candidate_views_hide_draft_intake_candidates() -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=9990001,
        fio="MAX Draft Candidate",
        city="Москва",
        initial_status=CandidateStatus.LEAD,
    )

    async with async_session() as session:
        db_candidate = await session.get(candidate_models.User, int(candidate.id))
        assert db_candidate is not None
        db_candidate.lifecycle_state = "draft"
        await session.commit()

    payload = await list_candidates(
        page=1,
        per_page=20,
        search="MAX Draft Candidate",
        city=None,
        is_active=None,
        rating=None,
        has_tests=None,
        has_messages=None,
        principal=Principal(type="admin", id=-1),
    )

    assert payload["total"] == 0
    assert await get_candidate_detail(candidate.id, principal=Principal(type="admin", id=-1)) is None


@pytest.mark.asyncio
async def test_candidate_views_degrade_gracefully_when_max_rollout_runtime_is_unavailable(monkeypatch) -> None:
    from backend.apps.admin_ui.services.candidates import helpers as candidate_helpers

    candidate = await candidate_services.create_or_update_user(
        telegram_id=9990002,
        fio="MAX Runtime Fallback",
        city="Москва",
        initial_status=CandidateStatus.LEAD,
    )

    candidate_helpers._candidate_max_rollout_runtime.cache_clear()

    def _raise_import_error():
        raise ImportError("max rollout runtime is unavailable")

    monkeypatch.setattr(candidate_helpers, "_candidate_max_rollout_runtime", _raise_import_error)

    payload = await list_candidates(
        page=1,
        per_page=20,
        search="MAX Runtime Fallback",
        city=None,
        is_active=None,
        rating=None,
        has_tests=None,
        has_messages=None,
        principal=Principal(type="admin", id=-1),
    )

    assert payload["total"] == 1
    assert payload["views"]["candidates"][0]["max_rollout"] is None

    detail = await api_candidate_detail_payload(candidate.id)
    assert detail is not None
    assert detail["max_rollout"] is None


@pytest.mark.asyncio
async def test_list_candidates_includes_responsible_recruiter_fallback_fields():
    async with async_session() as session:
        recruiter = Recruiter(name="Fallback Recruiter", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)
        recruiter_id = recruiter.id

    candidate = await candidate_services.create_or_update_user(
        telegram_id=999011,
        fio="Fallback Candidate",
        city="Москва",
        initial_status=CandidateStatus.TEST1_COMPLETED,
        responsible_recruiter_id=recruiter_id,
    )

    payload = await list_candidates(
        page=1,
        per_page=20,
        search="Fallback Candidate",
        city=None,
        is_active=None,
        rating=None,
        has_tests=None,
        has_messages=None,
        statuses=["test1_completed"],
        principal=Principal(type="admin", id=-1),
    )

    cards = payload["views"].get("candidates", [])
    card = next((item for item in cards if item.get("id") == candidate.id), None)
    assert card is not None
    assert card.get("recruiter_id") == recruiter_id
    assert card.get("recruiter_name") == "Fallback Recruiter"
    assert card.get("recruiter", {}).get("name") == "Fallback Recruiter"


@pytest.mark.asyncio
async def test_list_candidates_supports_canonical_kanban_state_filters() -> None:
    async with async_session() as session:
        city = City(name="Filter City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Filter Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

    candidate = await candidate_services.create_or_update_user(
        telegram_id=999901,
        fio="Canonical Filter Candidate",
        city="Filter City",
        initial_status=CandidateStatus.WAITING_SLOT,
    )

    async with async_session() as session:
        slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=SlotStatus.CONFIRMED_BY_CANDIDATE,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
        )
        session.add(slot)
        await session.commit()

    payload = await list_candidates(
        page=1,
        per_page=20,
        search="Canonical Filter Candidate",
        city=None,
        is_active=None,
        rating=None,
        has_tests=None,
        has_messages=None,
        pipeline="main",
        state_filters=["kanban:interview_confirmed"],
        principal=Principal(type="admin", id=-1),
    )

    assert payload["total"] == 1
    assert payload["filters"]["state"] == ["kanban:interview_confirmed"]
    card = payload["views"]["candidates"][0]
    assert card["operational_summary"]["kanban_column"] == "interview_confirmed"
    assert card["scheduling_summary"]["status"] == "confirmed"

    confirmed_column = next(
        column for column in payload["views"]["kanban"]["columns"] if column["slug"] == "interview_confirmed"
    )
    assert confirmed_column["target_status"] == "interview_confirmed"
    assert [candidate_card["id"] for candidate_card in confirmed_column["candidates"]] == [candidate.id]


@pytest.mark.asyncio
async def test_get_candidate_detail_marks_persisted_scheduling_split_brain_for_manual_repair() -> None:
    async with async_session() as session:
        city = City(name="Split Brain City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Split Brain Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

    candidate = await candidate_services.create_or_update_user(
        telegram_id=999912,
        fio="Persisted Conflict Candidate",
        city="Split Brain City",
        initial_status=CandidateStatus.INTERVIEW_SCHEDULED,
        responsible_recruiter_id=recruiter.id,
    )

    async with async_session() as session:
        stale_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        target_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=SlotStatus.FREE,
            purpose="interview",
        )
        session.add_all([stale_slot, target_slot])
        await session.commit()
        await session.refresh(target_slot)

        session.add(
            SlotAssignment(
                slot_id=target_slot.id,
                recruiter_id=recruiter.id,
                candidate_id=candidate.candidate_id,
                candidate_tg_id=candidate.telegram_id,
                candidate_tz="Europe/Moscow",
                status=SlotAssignmentStatus.CONFIRMED,
                confirmed_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    detail = await get_candidate_detail(candidate.id, principal=Principal(type="admin", id=-1))

    assert detail is not None
    scheduling_summary = detail["scheduling_summary"]
    issue_codes = {issue.get("code") for issue in scheduling_summary["issues"]}
    assert scheduling_summary["integrity_state"] == "needs_manual_repair"
    assert scheduling_summary["write_behavior"] == "needs_manual_repair"
    assert scheduling_summary["write_owner"] == "slot_assignment"
    assert scheduling_summary["assignment_owned"] is True
    assert scheduling_summary["slot_only_writes_allowed"] is False
    assert scheduling_summary["repairability"] == "repairable"
    assert scheduling_summary["manual_repair_reasons"] == []
    assert scheduling_summary["repair_options"][0]["action"] == "assignment_authoritative"
    assert scheduling_summary["repair_workflow"]["policy"] == "repairable"
    assert scheduling_summary["repair_workflow"]["conflict_class"] == "scheduling_split_brain"
    assert scheduling_summary["repair_workflow"]["allowed_actions"][0]["action"] == "assignment_authoritative"
    assert "scheduling_split_brain" in issue_codes
    assert detail["operational_summary"]["has_scheduling_conflict"] is True
    assert detail["candidate_next_action"]["primary_action"]["type"] == "repair_inconsistency"


@pytest.mark.asyncio
async def test_get_candidate_detail_exposes_manual_repair_workflow_for_multiple_active_assignments() -> None:
    async with async_session() as session:
        city = City(name="Manual Workflow City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Manual Workflow Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

    candidate = await candidate_services.create_or_update_user(
        telegram_id=999914,
        fio="Manual Workflow Candidate",
        city="Manual Workflow City",
        initial_status=CandidateStatus.WAITING_SLOT,
        responsible_recruiter_id=recruiter.id,
    )

    async with async_session() as session:
        first_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=SlotStatus.PENDING,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        second_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=SlotStatus.PENDING,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        session.add_all([first_slot, second_slot])
        await session.commit()
        await session.refresh(first_slot)
        await session.refresh(second_slot)

        session.add_all(
            [
                SlotAssignment(
                    slot_id=first_slot.id,
                    recruiter_id=recruiter.id,
                    candidate_id=None,
                    candidate_tg_id=candidate.telegram_id,
                    candidate_tz="Europe/Moscow",
                    status=SlotAssignmentStatus.OFFERED,
                ),
                SlotAssignment(
                    slot_id=second_slot.id,
                    recruiter_id=recruiter.id,
                    candidate_id=None,
                    candidate_tg_id=candidate.telegram_id,
                    candidate_tz="Europe/Moscow",
                    status=SlotAssignmentStatus.OFFERED,
                ),
            ]
        )
        await session.commit()

    detail = await get_candidate_detail(candidate.id, principal=Principal(type="admin", id=-1))
    assert detail is not None
    scheduling_summary = detail["scheduling_summary"]
    workflow = scheduling_summary["repair_workflow"]
    assert scheduling_summary["repairability"] == "manual_only"
    assert scheduling_summary["manual_repair_reasons"] == ["multiple_active_assignments"]
    assert workflow["policy"] == "manual_only"
    assert workflow["conflict_class"] == "multiple_active_assignments"
    assert workflow["allowed_actions"][0]["action"] == "resolve_to_active_assignment"
    assert workflow["allowed_actions"][0]["selection_options"]["assignments"]
    assert workflow["allowed_actions"][0]["required_confirmations"] == [
        "selected_assignment_is_canonical",
        "cancel_non_selected_active_assignments",
    ]
    assert detail["candidate_next_action"]["primary_action"]["type"] == "repair_inconsistency"


@pytest.mark.asyncio
async def test_get_candidate_detail_becomes_consistent_after_controlled_scheduling_repair() -> None:
    async with async_session() as session:
        city = City(name="Repair Detail City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Repair Detail Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

    candidate = await candidate_services.create_or_update_user(
        telegram_id=999913,
        fio="Repair Detail Candidate",
        city="Repair Detail City",
        initial_status=CandidateStatus.INTERVIEW_SCHEDULED,
        responsible_recruiter_id=recruiter.id,
    )

    async with async_session() as session:
        stale_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=1),
            duration_min=60,
            status=SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        target_slot = Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=2),
            duration_min=60,
            status=SlotStatus.FREE,
            purpose="interview",
        )
        session.add_all([stale_slot, target_slot])
        await session.commit()
        await session.refresh(target_slot)

        assignment = SlotAssignment(
            slot_id=target_slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=SlotAssignmentStatus.CONFIRMED,
            confirmed_at=datetime.now(timezone.utc),
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        assignment_id = assignment.id

    repair_result = await repair_slot_assignment_scheduling_conflict(
        assignment_id=assignment_id,
        repair_action="assignment_authoritative",
        performed_by_type="admin",
        performed_by_id=0,
    )
    assert repair_result.ok is True

    detail = await get_candidate_detail(candidate.id, principal=Principal(type="admin", id=-1))
    assert detail is not None
    scheduling_summary = detail["scheduling_summary"]
    assert scheduling_summary["integrity_state"] == "consistent"
    assert scheduling_summary["write_behavior"] == "allow"
    assert scheduling_summary["repairability"] == "not_needed"
    assert scheduling_summary["repair_options"] == []
    assert scheduling_summary["manual_repair_reasons"] == []
    assert scheduling_summary["repair_workflow"]["policy"] == "not_needed"
    assert scheduling_summary["repair_workflow"]["allowed_actions"] == []
    assert scheduling_summary["issues"] == []
    assert detail["operational_summary"]["has_scheduling_conflict"] is False


@pytest.mark.asyncio
async def test_list_candidates_canonical_filter_handles_test2_completion_when_legacy_status_lags() -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=999902,
        fio="Late Test2 Candidate",
        city="Москва",
        initial_status=CandidateStatus.TEST2_SENT,
    )

    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=999,
        final_score=100.0,
        rating="TEST2",
        total_time=120,
        question_data=[],
    )

    payload = await list_candidates(
        page=1,
        per_page=20,
        search="Late Test2 Candidate",
        city=None,
        is_active=None,
        rating=None,
        has_tests=None,
        has_messages=None,
        pipeline="main",
        state_filters=["kanban:test2_completed"],
        principal=Principal(type="admin", id=-1),
    )

    assert payload["total"] == 1
    card = payload["views"]["candidates"][0]
    assert card["status"]["slug"] == CandidateStatus.TEST2_SENT.value
    assert card["operational_summary"]["kanban_column"] == "test2_completed"
    issue_codes = {issue.get("code") for issue in card["state_reconciliation"]["issues"]}
    assert "candidate_status_stale_after_test2_pass" in issue_codes


@pytest.mark.asyncio
async def test_list_candidates_kanban_totals_match_visible_candidate_cards() -> None:
    async with async_session() as session:
        city = City(name="Consistency City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Consistency Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

    await candidate_services.create_or_update_user(
        telegram_id=999903,
        fio="Consistency Candidate Waiting",
        city="Consistency City",
        initial_status=CandidateStatus.WAITING_SLOT,
    )
    interview_candidate = await candidate_services.create_or_update_user(
        telegram_id=999904,
        fio="Consistency Candidate Interview",
        city="Consistency City",
        initial_status=CandidateStatus.WAITING_SLOT,
    )
    test2_candidate = await candidate_services.create_or_update_user(
        telegram_id=999905,
        fio="Consistency Candidate Test2",
        city="Consistency City",
        initial_status=CandidateStatus.TEST2_SENT,
    )

    await candidate_services.save_test_result(
        user_id=test2_candidate.id,
        raw_score=999,
        final_score=100.0,
        rating="TEST2",
        total_time=120,
        question_data=[],
    )

    async with async_session() as session:
        session.add(
            Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                tz_name=city.tz,
                start_utc=datetime.now(timezone.utc) + timedelta(days=1),
                duration_min=60,
                status=SlotStatus.CONFIRMED_BY_CANDIDATE,
                candidate_id=interview_candidate.candidate_id,
                candidate_tg_id=interview_candidate.telegram_id,
                candidate_fio=interview_candidate.fio,
                candidate_tz="Europe/Moscow",
            )
        )
        await session.commit()

    payload = await list_candidates(
        page=1,
        per_page=20,
        search="Consistency Candidate",
        city=None,
        is_active=None,
        rating=None,
        has_tests=None,
        has_messages=None,
        pipeline="main",
        principal=Principal(type="admin", id=-1),
    )

    cards = payload["views"]["candidates"]
    assert payload["total"] == 3
    assert len(cards) == 3

    expected_counts: dict[str, int] = {}
    for card in cards:
        slug = card["operational_summary"]["kanban_column"]
        expected_counts[slug] = expected_counts.get(slug, 0) + 1

    assert payload["summary"]["kanban_totals"]["incoming"] == expected_counts["incoming"]
    assert payload["summary"]["kanban_totals"]["interview_confirmed"] == expected_counts["interview_confirmed"]
    assert payload["summary"]["kanban_totals"]["test2_completed"] == expected_counts["test2_completed"]

    for column in payload["views"]["kanban"]["columns"]:
        slug = column["slug"]
        column_candidates = [candidate_card["id"] for candidate_card in column["candidates"]]
        expected_column_candidates = [
            card["id"] for card in cards if card["operational_summary"]["kanban_column"] == slug
        ]
        assert column["total"] == len(column_candidates)
        assert sorted(column_candidates) == sorted(expected_column_candidates)


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
async def test_candidate_detail_prefers_candidate_status_without_mutating_workflow_status():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=999004,
        fio="Workflow Detail",
        city="Москва",
    )

    async with async_session() as session:
        user = await session.get(candidate_models.User, candidate.id)
        assert user is not None
        user.candidate_status = CandidateStatus.INTRO_DAY_SCHEDULED
        user.workflow_status = WorkflowStatus.INTERVIEW_CONFIRMED.value
        await session.commit()

    detail = await get_candidate_detail(candidate.id)
    assert detail is not None
    assert detail["workflow_status"] == WorkflowStatus.ONBOARDING_DAY_SCHEDULED.value
    assert detail["workflow_status_label"] == "Назначен ознакомительный день"

    async with async_session() as session:
        refreshed = await session.get(candidate_models.User, candidate.id)
        assert refreshed is not None
        assert refreshed.workflow_status == WorkflowStatus.INTERVIEW_CONFIRMED.value


@pytest.mark.asyncio
async def test_candidate_detail_does_not_autofix_test2_status_on_read():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=999304,
        fio="Stable Test2 Status",
        city="Москва",
        initial_status=CandidateStatus.TEST2_SENT,
    )

    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=99,
        final_score=99.0,
        rating="TEST2",
        total_time=120,
        question_data=[],
    )

    detail = await get_candidate_detail(candidate.id)

    assert detail is not None
    assert detail["candidate_status_slug"] == CandidateStatus.TEST2_SENT.value
    assert detail["lifecycle_summary"]["stage"] == "waiting_intro_day"
    issue_codes = {
        issue.get("code")
        for issue in detail["state_reconciliation"]["issues"]
    }
    assert "candidate_status_stale_after_test2_pass" in issue_codes

    async with async_session() as session:
        refreshed = await session.get(candidate_models.User, candidate.id)
        assert refreshed is not None
        assert refreshed.candidate_status == CandidateStatus.TEST2_SENT


@pytest.mark.asyncio
async def test_candidate_detail_without_test2_data_keeps_not_started_state() -> None:
    candidate = await candidate_services.create_or_update_user(
        telegram_id=999305,
        fio="No Test2 Candidate",
        city="Москва",
        initial_status=CandidateStatus.LEAD,
    )

    detail = await get_candidate_detail(candidate.id)

    assert detail is not None
    assert detail["candidate_status_slug"] == CandidateStatus.LEAD.value
    assert detail["lifecycle_summary"]["stage"] == "lead"


@pytest.mark.asyncio
async def test_candidate_cohort_comparison_groups_similar_candidates():
    lead = await candidate_services.create_or_update_user(
        telegram_id=999201,
        fio="Lead Candidate",
        city="Москва",
        initial_status=CandidateStatus.TEST1_COMPLETED,
    )
    interview = await candidate_services.create_or_update_user(
        telegram_id=999202,
        fio="Interview Candidate",
        city="Москва",
        initial_status=CandidateStatus.INTERVIEW_CONFIRMED,
    )
    intro_day = await candidate_services.create_or_update_user(
        telegram_id=999203,
        fio="Intro Candidate",
        city="Москва",
        initial_status=CandidateStatus.INTRO_DAY_SCHEDULED,
    )

    await candidate_services.save_test_result(
        user_id=lead.id,
        raw_score=4,
        final_score=4.0,
        rating="TEST1",
        total_time=900,
        question_data=[],
    )
    await candidate_services.save_test_result(
        user_id=interview.id,
        raw_score=6,
        final_score=6.0,
        rating="TEST1",
        total_time=780,
        question_data=[],
    )
    await candidate_services.save_test_result(
        user_id=intro_day.id,
        raw_score=8,
        final_score=8.0,
        rating="TEST1",
        total_time=600,
        question_data=[],
    )

    async with async_session() as session:
        for user_id in (lead.id, interview.id, intro_day.id):
            user = await session.get(candidate_models.User, user_id)
            assert user is not None
            user.desired_position = "Оператор склада"
            user.hh_vacancy_id = "vacancy-cohort-1"
        await session.commit()

    payload = await get_candidate_cohort_comparison(int(intro_day.id), principal=Principal(type="admin", id=-1))

    assert payload is not None
    assert payload["cohort_label"] == "Оператор склада"
    assert payload["total_candidates"] == 3
    assert payload["rank"] == 1
    assert payload["test1"]["candidate"] == 8.0
    assert round(payload["test1"]["average"], 2) == 6.0
    assert payload["completion_time_sec"]["candidate"] == 600
    assert round(payload["completion_time_sec"]["average"], 2) == 760.0
    distribution = {item["key"]: item["count"] for item in payload["stage_distribution"]}
    assert distribution["lead"] == 1
    assert distribution["interview"] == 1
    assert distribution["intro_day"] == 1


@pytest.mark.asyncio
async def test_candidate_detail_prefers_city_intro_day_template():
    city_name = f"Город шаблона {uuid4().hex[:8]}"
    candidate = await candidate_services.create_or_update_user(
        telegram_id=999102,
        fio="Иванов Михаил Сергеевич",
        city=city_name,
        initial_status=CandidateStatus.TEST2_COMPLETED,
    )

    async with async_session() as session:
        city = City(
            name=city_name,
            tz="Europe/Moscow",
            active=True,
            intro_address="Волгоград, пр. Ленина, 1",
            contact_name="Ольга",
            contact_phone="+79990000000",
        )
        session.add(city)
        await session.flush()
        now = datetime.now(timezone.utc)
        session.add(
            MessageTemplate(
                key="intro_day_invitation",
                locale="ru",
                channel="tg",
                city_id=None,
                body_md="Общий шаблон intro day",
                version=1,
                is_active=True,
                updated_at=now,
                created_at=now,
            )
        )
        session.add(
            MessageTemplate(
                key="intro_day_invitation",
                locale="ru",
                channel="tg",
                city_id=city.id,
                body_md="Городской шаблон [Имя] {intro_address}",
                version=1,
                is_active=True,
                updated_at=now,
                created_at=now,
            )
        )
        await session.commit()

    detail = await get_candidate_detail(candidate.id)

    assert detail is not None
    assert detail["intro_day_template"] == "Городской шаблон [Имя] {intro_address}"
    assert detail["intro_day_template_context"]["intro_address"] == "Волгоград, пр. Ленина, 1"
    assert detail["intro_day_template_context"]["intro_contact"] == "Ольга, +79990000000"


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
async def test_candidate_detail_test_history_contains_attempt_details():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=999102,
        fio="Attempt History Candidate",
        city="Екатеринбург",
    )

    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=2,
        final_score=2.0,
        rating="TEST1",
        total_time=180,
        question_data=[
            {
                "question_index": 1,
                "question_text": "Q1",
                "correct_answer": "A",
                "user_answer": "A",
                "attempts_count": 1,
                "time_spent": 20,
                "is_correct": True,
                "overtime": False,
            },
            {
                "question_index": 2,
                "question_text": "Q2",
                "correct_answer": "B",
                "user_answer": "B",
                "attempts_count": 1,
                "time_spent": 25,
                "is_correct": True,
                "overtime": False,
            },
        ],
    )

    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=1,
        final_score=1.0,
        rating="TEST1",
        total_time=120,
        question_data=[
            {
                "question_index": 1,
                "question_text": "Q1 retry",
                "correct_answer": "A",
                "user_answer": "C",
                "attempts_count": 2,
                "time_spent": 30,
                "is_correct": False,
                "overtime": True,
            }
        ],
    )

    detail = await get_candidate_detail(candidate.id)
    assert detail is not None
    sections = {section["key"]: section for section in detail["test_sections"]}
    history = sections["test1"]["history"]
    assert len(history) == 2
    assert history[0]["details"]["stats"]["total_questions"] == 1
    assert history[0]["details"]["stats"]["overtime_questions"] == 1
    assert len(history[0]["details"]["questions"]) == 1
    assert history[1]["details"]["stats"]["total_questions"] == 2
    assert len(history[1]["details"]["questions"]) == 2


@pytest.mark.asyncio
async def test_candidate_detail_overrides_display_when_reschedule_requested(monkeypatch):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=999103,
        fio="Reschedule Detail Candidate",
        city="Екатеринбург",
        initial_status=CandidateStatus.SLOT_PENDING,
    )

    async def fake_reschedule_intent(*_args, **_kwargs):
        return RescheduleIntent(
            requested=True,
            created_at=datetime.now(timezone.utc).isoformat(),
            requested_start_utc=datetime(2031, 7, 16, 9, 0, tzinfo=timezone.utc).isoformat(),
            requested_end_utc=datetime(2031, 7, 16, 12, 0, tzinfo=timezone.utc).isoformat(),
            requested_tz="Europe/Moscow",
            candidate_comment="Лучше утром",
            source="bot_state",
        )

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.candidates.get_candidate_reschedule_intent",
        fake_reschedule_intent,
    )

    detail = await get_candidate_detail(candidate.id)
    assert detail is not None
    assert detail["candidate_status_slug"] == CandidateStatus.SLOT_PENDING.value
    assert detail["candidate_status_display"] == "Запросил другое время"
    assert detail["candidate_status_color"] == "warning"
    assert detail["stage"] == "Запросил другое время"

    payload = await api_candidate_detail_payload(candidate.id)
    assert payload is not None
    assert payload["candidate_status_display"] == "Запросил другое время"
    assert payload["candidate_status_color"] == "warning"
    assert payload["stage"] == "Запросил другое время"
    assert payload["reschedule_request"]["requested_start_utc"] == "2031-07-16T09:00:00+00:00"
    assert payload["reschedule_request"]["requested_end_utc"] == "2031-07-16T12:00:00+00:00"
    assert payload["reschedule_request"]["requested_tz"] == "Europe/Moscow"
    assert payload["reschedule_request"]["candidate_comment"] == "Лучше утром"


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


def test_map_to_workflow_status_prefers_candidate_status_over_stale_workflow():
    user = SimpleNamespace(
        id=101,
        candidate_status=CandidateStatus.INTRO_DAY_SCHEDULED,
        workflow_status=WorkflowStatus.INTERVIEW_CONFIRMED.value,
    )

    mapped = _map_to_workflow_status(user)
    assert mapped == WorkflowStatus.ONBOARDING_DAY_SCHEDULED


def test_map_to_workflow_status_intro_day_scheduled_is_not_confirmed():
    user = SimpleNamespace(
        id=102,
        candidate_status=CandidateStatus.INTRO_DAY_SCHEDULED.value,
        workflow_status=None,
    )

    mapped = _map_to_workflow_status(user)
    assert mapped == WorkflowStatus.ONBOARDING_DAY_SCHEDULED


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
async def test_intro_day_candidate_not_shown_in_interview_pipeline_even_with_interview_slot():
    candidate = await candidate_services.create_or_update_user(
        telegram_id=900111,
        fio="Dual Stage Candidate",
        city="Москва",
    )

    async with async_session() as session:
        city = City(name="Dual Stage City", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Dual Stage Recruiter", tz="Europe/Moscow", active=True)
        session.add_all([city, recruiter])
        await session.flush()
        user = await session.get(candidate_models.User, candidate.id)
        assert user is not None
        user.candidate_status = CandidateStatus.INTRO_DAY_SCHEDULED

        session.add(
            Slot(
                recruiter_id=recruiter.id,
                city_id=city.id,
                start_utc=datetime.now(timezone.utc) + timedelta(hours=4),
                status=SlotStatus.BOOKED,
                candidate_tg_id=candidate.telegram_id,
                candidate_fio=candidate.fio,
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
                candidate_tg_id=candidate.telegram_id,
                candidate_fio=candidate.fio,
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
    assert interview_payload["total"] == 0

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


@pytest.mark.asyncio
async def test_recruiter_can_update_unassigned_candidate_in_city_scope():
    async with async_session() as session:
        city = City(name="Воронеж", tz="Europe/Moscow", active=True)
        recruiter = Recruiter(name="Scoped Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.flush()
        recruiter_id = recruiter.id
        await session.commit()

    candidate = await candidate_services.create_or_update_user(
        telegram_id=991001,
        fio="Scoped Candidate",
        city="Воронеж",
    )

    ok, message, stored_status, _ = await update_candidate_status(
        candidate.id,
        "interview_declined",
        principal=Principal(type="recruiter", id=recruiter_id),
    )

    assert ok is True
    assert message == "Статус обновлён"
    assert stored_status == "interview_declined"
    async with async_session() as session:
        refreshed = await session.get(candidate_models.User, candidate.id)
        assert refreshed is not None
        assert refreshed.responsible_recruiter_id == recruiter_id


@pytest.mark.asyncio
async def test_recruiter_can_update_candidate_owned_by_another_recruiter_in_city_scope():
    async with async_session() as session:
        city = City(name="Томск", tz="Asia/Tomsk", active=True)
        owner = Recruiter(name="Owner Recruiter", tz="Asia/Tomsk", active=True)
        viewer = Recruiter(name="Viewer Recruiter", tz="Asia/Tomsk", active=True)
        owner.cities.append(city)
        viewer.cities.append(city)
        session.add_all([city, owner, viewer])
        await session.flush()
        owner_id = owner.id
        viewer_id = viewer.id
        await session.commit()

    candidate = await candidate_services.create_or_update_user(
        telegram_id=991002,
        fio="Foreign Candidate",
        city="Томск",
    )
    async with async_session() as session:
        db_candidate = await session.get(candidate_models.User, candidate.id)
        assert db_candidate is not None
        db_candidate.responsible_recruiter_id = owner_id
        await session.commit()

    ok, message, stored_status, _ = await update_candidate_status(
        candidate.id,
        "interview_declined",
        principal=Principal(type="recruiter", id=viewer_id),
    )

    assert ok is True
    assert message == "Статус обновлён"
    assert stored_status == "interview_declined"


@pytest.mark.asyncio
async def test_recruiter_cannot_update_candidate_outside_city_scope():
    async with async_session() as session:
        city_owner = City(name="Тюмень", tz="Asia/Yekaterinburg", active=True)
        city_viewer = City(name="Псков", tz="Europe/Moscow", active=True)
        owner = Recruiter(name="Owner Outside City", tz="Asia/Yekaterinburg", active=True)
        viewer = Recruiter(name="Viewer Outside City", tz="Europe/Moscow", active=True)
        owner.cities.append(city_owner)
        viewer.cities.append(city_viewer)
        session.add_all([city_owner, city_viewer, owner, viewer])
        await session.flush()
        owner_id = owner.id
        viewer_id = viewer.id
        await session.commit()

    candidate = await candidate_services.create_or_update_user(
        telegram_id=991003,
        fio="Outside City Candidate",
        city="Тюмень",
    )
    async with async_session() as session:
        db_candidate = await session.get(candidate_models.User, candidate.id)
        assert db_candidate is not None
        db_candidate.responsible_recruiter_id = owner_id
        await session.commit()

    ok, message, stored_status, _ = await update_candidate_status(
        candidate.id,
        "interview_declined",
        principal=Principal(type="recruiter", id=viewer_id),
    )

    assert ok is False
    assert message == "Кандидат не найден"
    assert stored_status is None
