from __future__ import annotations

from datetime import datetime, timedelta, timezone

import backend.apps.admin_ui.services.candidates.lifecycle_use_cases as lifecycle_use_cases
import pytest
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import (
    CandidateJourneySession,
    CandidateJourneyStepState,
    TestResult,
    User,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.status_service import StatusTransitionError
from backend.domain.candidates.test1_shared import TEST1_STEP_KEY
from sqlalchemy import select


async def _create_candidate(
    *,
    telegram_id: int,
    fio: str,
    status: CandidateStatus,
) -> User:
    return await candidate_services.create_or_update_user(
        telegram_id=telegram_id,
        fio=fio,
        city="Москва",
        username=f"user_{telegram_id}",
        initial_status=status,
    )


async def _create_candidate_slot(
    candidate: User,
    *,
    purpose: str,
    status: str,
    offset_days: int = 1,
) -> int:
    async with async_session() as session:
        city = models.City(name=f"Москва {candidate.id}", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name=f"Recruiter {candidate.id}", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=datetime.now(timezone.utc) + timedelta(days=offset_days),
            duration_min=60,
            status=status,
            purpose=purpose,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz=city.tz,
            candidate_city_id=city.id,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)
        return int(slot.id)


async def _create_test2_result(
    user_id: int,
    *,
    raw_score: int,
    final_score: float,
    created_at: datetime | None = None,
) -> None:
    async with async_session() as session:
        result = TestResult(
            user_id=user_id,
            raw_score=raw_score,
            final_score=final_score,
            rating="TEST2",
            source="admin_test",
            total_time=120,
            created_at=created_at or datetime.now(timezone.utc),
        )
        session.add(result)
        await session.commit()


async def _seed_test1_attempt(
    candidate: User,
    *,
    completed: bool = True,
    journey_step_key: str = "test1_completed",
) -> int:
    async with async_session() as session:
        user = await session.get(User, candidate.id)
        assert user is not None
        test_result = TestResult(
            user_id=user.id,
            raw_score=11,
            final_score=11.0,
            rating="TEST1",
            source="admin_test",
            total_time=180,
        )
        session.add(test_result)
        await session.flush()
        journey_session = CandidateJourneySession(
            candidate_id=user.id,
            journey_key="candidate_portal",
            journey_version="v1",
            entry_channel="max",
            current_step_key=journey_step_key,
            last_surface="max_miniapp",
            last_auth_method="max_init_data",
            payload_json={
                "candidate_access": {
                    "allowed_next_actions": ["select_interview_slot"],
                    "booking_context": {
                        "city_id": 1,
                        "city_name": "Москва",
                        "recruiter_id": 1,
                        "recruiter_name": "Recruiter",
                    },
                    "chat_cursor": {"state": "completed"},
                    "test1": {
                        "test_result_id": int(test_result.id),
                        "required_next_action": "select_interview_slot",
                    },
                    "active_surface": "max_chat",
                }
            },
        )
        session.add(journey_session)
        await session.flush()
        step_state = CandidateJourneyStepState(
            session_id=journey_session.id,
            step_key=TEST1_STEP_KEY,
            step_type="form",
            status="completed" if completed else "in_progress",
            payload_json={
                "draft": {
                    "question_ids": ["fio", "city", "age"],
                    "answers": {"fio": "Иванов Иван Иванович", "city": "Москва", "age": "23"},
                    "city_id": 1,
                    "city_name": "Москва",
                    "candidate_tz": "Europe/Moscow",
                },
                "completion": {
                    "completed": completed,
                    "test_result_id": int(test_result.id),
                    "required_next_action": "select_interview_slot",
                    "current_step_key": journey_step_key,
                    "screening_decision": {"outcome": "invite_to_interview"},
                    "interview_offer": {"city_id": 1, "city_name": "Москва"},
                },
            },
        )
        session.add(step_state)
        await session.commit()
        return int(test_result.id)


@pytest.mark.asyncio
async def test_execute_send_to_test2_allows_interview_scheduled_and_records_slot_outcome() -> None:
    candidate = await _create_candidate(
        telegram_id=920001,
        fio="Interview Scheduled Candidate",
        status=CandidateStatus.INTERVIEW_SCHEDULED,
    )
    slot_id = await _create_candidate_slot(
        candidate,
        purpose="interview",
        status=models.SlotStatus.BOOKED,
    )

    result = await lifecycle_use_cases.execute_send_to_test2(
        candidate.id,
        principal=None,
        bot_service=None,
        action_key="interview_outcome_passed",
    )

    assert result.ok is True
    assert result.status == CandidateStatus.TEST2_SENT.value
    assert (result.detail or {})["candidate_status_slug"] == CandidateStatus.TEST2_SENT.value

    async with async_session() as session:
        user = await session.get(User, candidate.id)
        slot = await session.get(models.Slot, slot_id)
    assert user is not None
    assert user.candidate_status == CandidateStatus.TEST2_SENT
    assert slot is not None
    assert slot.interview_outcome == "success"


@pytest.mark.asyncio
async def test_execute_send_to_test2_allows_interview_confirmed() -> None:
    candidate = await _create_candidate(
        telegram_id=920002,
        fio="Interview Confirmed Candidate",
        status=CandidateStatus.INTERVIEW_CONFIRMED,
    )
    await _create_candidate_slot(
        candidate,
        purpose="interview",
        status=models.SlotStatus.CONFIRMED_BY_CANDIDATE,
    )

    result = await lifecycle_use_cases.execute_send_to_test2(
        candidate.id,
        principal=None,
        bot_service=None,
        action_key="interview_passed",
    )

    assert result.ok is True
    assert result.status == CandidateStatus.TEST2_SENT.value


@pytest.mark.asyncio
async def test_execute_send_to_test2_blocks_without_interview_scheduling() -> None:
    candidate = await _create_candidate(
        telegram_id=920003,
        fio="Missing Interview Slot",
        status=CandidateStatus.INTERVIEW_SCHEDULED,
    )

    result = await lifecycle_use_cases.execute_send_to_test2(
        candidate.id,
        principal=None,
        bot_service=None,
    )

    assert result.ok is False
    assert result.error == "missing_interview_scheduling"
    assert result.status_code == 409


@pytest.mark.asyncio
async def test_execute_send_to_test2_blocks_on_scheduling_conflict(monkeypatch) -> None:
    candidate = await _create_candidate(
        telegram_id=920004,
        fio="Scheduling Conflict Candidate",
        status=CandidateStatus.INTERVIEW_SCHEDULED,
    )
    detail = await lifecycle_use_cases.get_candidate_detail(candidate.id, principal=None)
    assert detail is not None
    await _create_candidate_slot(
        candidate,
        purpose="interview",
        status=models.SlotStatus.BOOKED,
    )
    detail = await lifecycle_use_cases.get_candidate_detail(candidate.id, principal=None)
    assert detail is not None

    async def _fake_detail(*_args, **_kwargs):
        conflict_detail = dict(detail)
        conflict_operational = dict(conflict_detail.get("operational_summary") or {})
        conflict_operational["has_scheduling_conflict"] = True
        conflict_detail["operational_summary"] = conflict_operational
        return conflict_detail

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.candidates.lifecycle_use_cases.get_candidate_detail",
        _fake_detail,
    )

    result = await lifecycle_use_cases.execute_send_to_test2(
        candidate.id,
        principal=None,
        bot_service=None,
        action_key="interview_outcome_passed",
    )

    assert result.ok is False
    assert result.error == "scheduling_conflict"
    assert result.status_code == 409


@pytest.mark.asyncio
async def test_execute_send_to_test2_surfaces_partial_transition_requires_repair(monkeypatch) -> None:
    candidate = await _create_candidate(
        telegram_id=920005,
        fio="Partial Transition Candidate",
        status=CandidateStatus.INTERVIEW_SCHEDULED,
    )
    await _create_candidate_slot(
        candidate,
        purpose="interview",
        status=models.SlotStatus.BOOKED,
    )

    async def _fake_set_slot_outcome(*_args, **_kwargs):
        return True, "Исход сохранен", "success", None

    async def _fake_apply_candidate_status(*_args, **_kwargs):
        raise StatusTransitionError("boom")

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.candidates.lifecycle_use_cases.set_slot_outcome",
        _fake_set_slot_outcome,
    )
    monkeypatch.setattr(
        "backend.apps.admin_ui.services.candidates.lifecycle_use_cases.apply_candidate_status",
        _fake_apply_candidate_status,
    )

    result = await lifecycle_use_cases.execute_send_to_test2(
        candidate.id,
        principal=None,
        bot_service=None,
        action_key="interview_outcome_passed",
    )

    assert result.ok is False
    assert result.error == "partial_transition_requires_repair"
    assert result.status_code == 409


@pytest.mark.asyncio
async def test_execute_mark_test2_completed_requires_passed_result() -> None:
    candidate = await _create_candidate(
        telegram_id=920006,
        fio="Passed Test2 Candidate",
        status=CandidateStatus.TEST2_SENT,
    )
    await _create_test2_result(candidate.id, raw_score=999, final_score=100.0)

    result = await lifecycle_use_cases.execute_mark_test2_completed(
        candidate.id,
        principal=None,
    )

    assert result.ok is True
    assert result.status == CandidateStatus.TEST2_COMPLETED.value
    assert (result.detail or {}).get("lifecycle_summary", {}).get("stage") == "waiting_intro_day"


@pytest.mark.asyncio
async def test_execute_mark_test2_completed_blocks_without_result() -> None:
    candidate = await _create_candidate(
        telegram_id=920007,
        fio="No Test2 Result Candidate",
        status=CandidateStatus.TEST2_SENT,
    )

    result = await lifecycle_use_cases.execute_mark_test2_completed(
        candidate.id,
        principal=None,
    )

    assert result.ok is False
    assert result.error == "test2_not_passed"
    assert result.status_code == 409


@pytest.mark.asyncio
async def test_execute_mark_test2_completed_blocks_when_latest_result_failed() -> None:
    candidate = await _create_candidate(
        telegram_id=920008,
        fio="Failed Latest Test2 Candidate",
        status=CandidateStatus.TEST2_SENT,
    )
    now = datetime.now(timezone.utc)
    await _create_test2_result(
        candidate.id,
        raw_score=999,
        final_score=100.0,
        created_at=now - timedelta(minutes=5),
    )
    await _create_test2_result(
        candidate.id,
        raw_score=0,
        final_score=0.0,
        created_at=now,
    )

    result = await lifecycle_use_cases.execute_mark_test2_completed(
        candidate.id,
        principal=None,
    )

    assert result.ok is False
    assert result.error == "test2_not_passed"
    assert result.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "initial_status",
    [
        CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
        CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
    ],
)
async def test_execute_finalize_hired_allows_intro_day_confirmed_states(
    initial_status: CandidateStatus,
) -> None:
    candidate = await _create_candidate(
        telegram_id=920009 if initial_status == CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY else 920010,
        fio=f"Hired {initial_status.value}",
        status=initial_status,
    )

    result = await lifecycle_use_cases.execute_finalize_hired(
        candidate.id,
        principal=None,
        action_key="mark_hired",
    )

    assert result.ok is True
    assert result.status == CandidateStatus.HIRED.value


@pytest.mark.asyncio
async def test_execute_finalize_hired_blocks_on_scheduling_conflict(monkeypatch) -> None:
    candidate = await _create_candidate(
        telegram_id=920011,
        fio="Conflict Finalize Candidate",
        status=CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
    )
    detail = await lifecycle_use_cases.get_candidate_detail(candidate.id, principal=None)
    assert detail is not None

    async def _fake_detail(*_args, **_kwargs):
        conflict_detail = dict(detail)
        conflict_operational = dict(conflict_detail.get("operational_summary") or {})
        conflict_operational["has_scheduling_conflict"] = True
        conflict_detail["operational_summary"] = conflict_operational
        return conflict_detail

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.candidates.lifecycle_use_cases.get_candidate_detail",
        _fake_detail,
    )

    result = await lifecycle_use_cases.execute_finalize_hired(
        candidate.id,
        principal=None,
        action_key="mark_hired",
    )

    assert result.ok is False
    assert result.error == "scheduling_conflict"


@pytest.mark.asyncio
async def test_execute_finalize_not_hired_releases_intro_day_slots_and_marks_inactive() -> None:
    candidate = await _create_candidate(
        telegram_id=920012,
        fio="Finalize Not Hired Candidate",
        status=CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
    )
    slot_id = await _create_candidate_slot(
        candidate,
        purpose="intro_day",
        status=models.SlotStatus.BOOKED,
    )

    result = await lifecycle_use_cases.execute_finalize_not_hired(
        candidate.id,
        principal=None,
        reason="не засчитан",
        comment="не явился",
        action_key="mark_not_hired",
    )

    assert result.ok is True
    assert result.status == CandidateStatus.NOT_HIRED.value
    assert result.dispatch is not None

    async with async_session() as session:
        user = await session.get(User, candidate.id)
        slot = await session.get(models.Slot, slot_id)
    assert user is not None
    assert user.candidate_status == CandidateStatus.NOT_HIRED
    assert user.is_active is False
    assert slot is not None
    assert slot.status == models.SlotStatus.FREE
    assert slot.candidate_id is None


@pytest.mark.asyncio
async def test_execute_finalize_not_hired_blocks_invalid_state() -> None:
    candidate = await _create_candidate(
        telegram_id=920013,
        fio="Invalid Finalize Candidate",
        status=CandidateStatus.WAITING_SLOT,
    )

    result = await lifecycle_use_cases.execute_finalize_not_hired(
        candidate.id,
        principal=None,
        reason="manual",
        action_key="mark_not_hired",
    )

    assert result.ok is False
    assert result.error == "invalid_transition"
    assert result.status_code == 409


@pytest.mark.asyncio
async def test_execute_restart_test1_resets_current_attempt_and_reopens_candidate() -> None:
    candidate = await _create_candidate(
        telegram_id=920014,
        fio="Restart Test1 Candidate",
        status=CandidateStatus.NOT_HIRED,
    )
    previous_result_id = await _seed_test1_attempt(candidate)

    result = await lifecycle_use_cases.execute_restart_test1(
        candidate.id,
        principal=None,
        action_key="restart_test1",
        reason="candidate_reapplied",
    )

    assert result.ok is True
    assert result.status == CandidateStatus.INVITED.value

    async with async_session() as session:
        user = await session.get(User, candidate.id)
        journey_session = await session.scalar(
            select(CandidateJourneySession)
            .where(CandidateJourneySession.candidate_id == candidate.id)
            .order_by(CandidateJourneySession.id.desc())
            .limit(1)
        )
        step_state = await session.scalar(
            select(CandidateJourneyStepState)
            .where(
                CandidateJourneyStepState.session_id == journey_session.id,
                CandidateJourneyStepState.step_key == TEST1_STEP_KEY,
            )
        )
    assert user is not None
    assert user.candidate_status == CandidateStatus.INVITED
    assert user.is_active is True
    assert user.rejection_reason is None
    assert user.final_outcome_reason is None
    assert journey_session is not None
    assert journey_session.current_step_key == TEST1_STEP_KEY
    assert journey_session.session_version >= 2
    assert journey_session.last_access_session_id is None
    assert journey_session.last_surface is None
    candidate_access = dict(journey_session.payload_json or {}).get("candidate_access") or {}
    assert "booking_context" not in candidate_access
    assert "test1" not in candidate_access
    assert candidate_access.get("history")
    assert step_state is not None
    history = list((step_state.payload_json or {}).get("history") or [])
    assert history
    assert history[-1]["test_result_id"] == previous_result_id
    assert history[-1]["required_next_action"] == "select_interview_slot"


@pytest.mark.asyncio
async def test_execute_restart_test1_blocks_when_candidate_has_active_scheduling() -> None:
    candidate = await _create_candidate(
        telegram_id=920015,
        fio="Restart Blocked Candidate",
        status=CandidateStatus.TEST1_COMPLETED,
    )
    await _seed_test1_attempt(candidate)
    await _create_candidate_slot(
        candidate,
        purpose="interview",
        status=models.SlotStatus.BOOKED,
    )

    result = await lifecycle_use_cases.execute_restart_test1(
        candidate.id,
        principal=None,
        action_key="restart_test1",
    )

    assert result.ok is False
    assert result.error == "active_scheduling_exists"
    assert result.status_code == 409
