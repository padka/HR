from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import backend.apps.admin_ui.services.candidates.lifecycle_use_cases as lifecycle_use_cases
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import TestResult, User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.status_service import StatusTransitionError


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
