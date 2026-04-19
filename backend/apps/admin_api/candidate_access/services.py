"""Shared candidate-facing access services for external surfaces."""

from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.apps.bot.config import (
    MAX_ATTEMPTS,
    PASS_THRESHOLD,
    TEST2_QUESTIONS,
    TIME_LIMIT,
    get_questions_bank_version,
    refresh_questions_bank,
)
from backend.apps.bot.services.base import REPORTS_DIR, calculate_score
from backend.apps.bot.services.test2_flow import get_rating
from backend.apps.bot.services.broadcast import notify_recruiters_manual_availability
from backend.domain.candidates.journey import LIFECYCLE_DRAFT
from backend.domain.candidates.max_launch_invites import create_max_launch_invite
from backend.domain.candidates.models import (
    CandidateJourneyEvent,
    CandidateJourneySession,
    CandidateJourneyStepState,
    CandidateJourneyStepStatus,
    User,
)
from backend.domain.candidates.phones import normalize_candidate_phone
from backend.domain.candidates.services import save_test_result, update_candidate_reports
from backend.domain.candidates.scheduling_integrity import (
    WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR,
    load_candidate_scheduling_integrity,
)
from backend.domain.candidates.services import save_manual_slot_response_for_user
from backend.domain import analytics
from backend.domain.candidates.test1_shared import (
    BOOKING_STEP_KEY,
    NEXT_ACTION_SELECT_INTERVIEW_SLOT,
    TEST1_STEP_KEY,
    complete_test1_for_candidate,
    materialize_test1_questions,
    merge_test1_answers,
    serialize_step_payload,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.status_service import update_candidate_status_by_candidate_id
from backend.domain.models import (
    DEFAULT_INTERVIEW_DURATION_MIN,
    Application,
    City,
    Recruiter,
    Slot,
    SlotStatus,
    SlotStatusTransitionError,
    enforce_slot_transition,
)
from backend.domain.repositories import (
    confirm_slot_by_candidate,
    get_active_recruiters_for_city,
    get_candidate_cities,
    get_recruiters_free_slots_summary,
    reject_slot,
)
from backend.domain.slot_service import reserve_slot as reserve_domain_slot

if TYPE_CHECKING:
    from backend.apps.admin_api.candidate_access.auth import CandidateAccessPrincipal

ACTIVE_INTERVIEW_SLOT_STATUSES = {
    SlotStatus.PENDING,
    SlotStatus.BOOKED,
    SlotStatus.CONFIRMED,
    SlotStatus.CONFIRMED_BY_CANDIDATE,
}

logger = logging.getLogger(__name__)

BOOKING_CONTEXT_KEY = "booking_context"
BOOKING_CONTEXT_SOURCE_EXPLICIT = "explicit"
BOOKING_CONTEXT_SOURCE_TEST1 = "test1_prefill"
BOOKING_CONTEXT_SOURCE_PROFILE = "profile"
TEST2_STEP_KEY = "test2"
INTRO_DAY_STEP_KEY = "intro_day"


@dataclass(frozen=True)
class CandidateProfile:
    candidate: User
    city_id: int | None
    city_name: str | None
    timezone_name: str
    telegram_ids: tuple[int, ...]


@dataclass(frozen=True)
class CandidateJourneyEnvelope:
    profile: CandidateProfile
    journey_session: CandidateJourneySession
    active_booking: Slot | None


@dataclass(frozen=True)
class CandidateTest1Envelope:
    profile: CandidateProfile
    journey_session: CandidateJourneySession
    questions: list[dict[str, Any]]
    draft_answers: dict[str, str]
    is_completed: bool
    screening_decision: dict[str, Any] | None
    interview_offer: dict[str, Any] | None
    required_next_action: str | None


@dataclass(frozen=True)
class CandidateBookingCity:
    city_id: int
    city_name: str
    timezone_name: str
    has_available_recruiters: bool
    available_recruiters: int
    available_slots: int


@dataclass(frozen=True)
class CandidateBookingRecruiter:
    recruiter_id: int
    recruiter_name: str
    timezone_name: str
    available_slots: int
    next_slot_utc: datetime | None
    city_id: int


@dataclass(frozen=True)
class CandidateBookingContextEnvelope:
    profile: CandidateProfile
    journey_session: CandidateJourneySession
    city_id: int | None
    city_name: str | None
    recruiter_id: int | None
    recruiter_name: str | None
    recruiter_tz: str | None
    source: str
    is_explicit: bool


@dataclass(frozen=True)
class CandidateContactBindEnvelope:
    status: str
    message: str
    candidate: User | None = None
    application_id: int | None = None
    start_param: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class CandidateManualAvailabilityEnvelope:
    status: str
    message: str
    recruiters_notified: bool


@dataclass(frozen=True)
class CandidateTest2Envelope:
    profile: CandidateProfile
    journey_session: CandidateJourneySession
    questions: list[dict[str, Any]]
    current_question_index: int | None
    attempts: dict[str, Any]
    is_started: bool
    is_completed: bool
    score: float | None
    correct_answers: int | None
    total_questions: int
    passed: bool | None
    rating: str | None
    required_next_action: str | None
    result_message: str | None


@dataclass(frozen=True)
class CandidateIntroDayEnvelope:
    profile: CandidateProfile
    journey_session: CandidateJourneySession
    slot: Slot | None
    city_name: str | None
    intro_address: str | None
    intro_contact: str | None
    contact_name: str | None
    contact_phone: str | None
    recruiter_name: str | None
    confirm_state: str | None


def _known_telegram_ids(candidate: User) -> tuple[int, ...]:
    ids: set[int] = set()
    for raw in (candidate.telegram_id, candidate.telegram_user_id):
        if raw is None:
            continue
        try:
            ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    return tuple(sorted(ids))


def _candidate_slot_filters(candidate: User) -> list:
    filters = [Slot.candidate_id == candidate.candidate_id]
    telegram_ids = _known_telegram_ids(candidate)
    if telegram_ids:
        filters.append(Slot.candidate_tg_id.in_(telegram_ids))
    return filters


def _booking_conflict_error(result_status: str) -> HTTPException:
    if result_status == "duplicate_candidate":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate already has an active interview booking.",
        )
    if result_status == "already_reserved":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking already exists for this candidate.",
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Slot is already booked. Please choose another slot.",
    )


async def ensure_candidate_slot_write_allowed(
    session: AsyncSession,
    candidate: User,
) -> None:
    integrity = await load_candidate_scheduling_integrity(session, candidate)
    if integrity.get("slot_only_writes_allowed"):
        return
    if integrity.get("write_behavior") == WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scheduling conflict requires manual repair before candidate-access slot update.",
        )
    if integrity.get("assignment_owned"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scheduling is managed by SlotAssignment. Candidate-access slot-only mutation is not allowed.",
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Scheduling state cannot be updated through slot-only candidate access flow.",
    )


def _candidate_access_payload(journey_session: CandidateJourneySession) -> dict[str, Any]:
    payload = dict(journey_session.payload_json or {})
    candidate_access_payload = payload.get("candidate_access")
    return dict(candidate_access_payload or {})


def _replace_candidate_access_payload(
    journey_session: CandidateJourneySession,
    candidate_access_payload: dict[str, Any],
) -> None:
    payload = dict(journey_session.payload_json or {})
    payload["candidate_access"] = dict(candidate_access_payload or {})
    journey_session.payload_json = payload


def _booking_context_payload(journey_session: CandidateJourneySession) -> dict[str, Any]:
    candidate_access_payload = _candidate_access_payload(journey_session)
    booking_context = candidate_access_payload.get(BOOKING_CONTEXT_KEY)
    return dict(booking_context or {})


def _persist_booking_context(
    journey_session: CandidateJourneySession,
    *,
    city_id: int | None,
    city_name: str | None,
    recruiter_id: int | None,
    recruiter_name: str | None,
    recruiter_tz: str | None,
    source: str,
) -> None:
    candidate_access_payload = _candidate_access_payload(journey_session)
    candidate_access_payload[BOOKING_CONTEXT_KEY] = {
        "version": 1,
        "city_id": city_id,
        "city_name": city_name,
        "recruiter_id": recruiter_id,
        "recruiter_name": recruiter_name,
        "recruiter_tz": recruiter_tz,
        "source": source,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    _replace_candidate_access_payload(journey_session, candidate_access_payload)


async def _load_city(
    session: AsyncSession,
    city_id: int | None,
) -> City | None:
    if city_id is None:
        return None
    city = await session.get(City, int(city_id))
    if city is None or not city.active:
        return None
    return city


async def _load_recruiter(
    session: AsyncSession,
    recruiter_id: int | None,
) -> Recruiter | None:
    if recruiter_id is None:
        return None
    recruiter = await session.get(Recruiter, int(recruiter_id))
    if recruiter is None or not recruiter.active:
        return None
    return recruiter


def _allowed_next_actions(journey_session: CandidateJourneySession) -> set[str]:
    candidate_access_payload = _candidate_access_payload(journey_session)
    actions = candidate_access_payload.get("allowed_next_actions") or []
    return {str(action) for action in actions if str(action or "").strip()}


def _extract_completion_payload(step_state: CandidateJourneyStepState | None) -> dict[str, Any] | None:
    if step_state is None:
        return None
    payload = dict(step_state.payload_json or {})
    completion = payload.get("completion")
    if isinstance(completion, dict) and completion.get("completed"):
        return completion
    return None


async def _booking_context_prefill(
    session: AsyncSession,
    *,
    journey_session: CandidateJourneySession,
    profile: CandidateProfile,
) -> tuple[int | None, str | None, str]:
    step_state = await _load_test1_step_state(session, journey_session.id, for_update=False)
    if step_state is not None:
        payload = dict(step_state.payload_json or {})
        draft = dict(payload.get("draft") or {})
        completion = _extract_completion_payload(step_state) or {}
        interview_offer = dict(completion.get("interview_offer") or {})
        city_id_raw = (
            draft.get("city_id")
            if draft.get("city_id") is not None
            else interview_offer.get("city_id")
        )
        city_name_raw = (
            draft.get("city_name")
            if draft.get("city_name")
            else interview_offer.get("city_name")
        )
        try:
            city_id = int(city_id_raw) if city_id_raw is not None else None
        except (TypeError, ValueError):
            city_id = None
        city_name = str(city_name_raw).strip() if city_name_raw else None
        if city_id is not None or city_name is not None:
            if city_name is None and city_id is not None:
                city = await _load_city(session, city_id)
                city_name = city.name_plain if city is not None else None
            return city_id, city_name, BOOKING_CONTEXT_SOURCE_TEST1

    return profile.city_id, profile.city_name, BOOKING_CONTEXT_SOURCE_PROFILE


async def load_candidate_booking_context(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> CandidateBookingContextEnvelope:
    profile = await load_candidate_profile(session, principal)
    journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
    if journey_session is None or journey_session.candidate_id != profile.candidate.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")

    explicit = _booking_context_payload(journey_session)
    source = str(explicit.get("source") or "").strip()
    if explicit:
        city = await _load_city(session, explicit.get("city_id"))
        recruiter = await _load_recruiter(session, explicit.get("recruiter_id"))
        return CandidateBookingContextEnvelope(
            profile=profile,
            journey_session=journey_session,
            city_id=int(city.id) if city is not None else None,
            city_name=city.name_plain if city is not None else (str(explicit.get("city_name")).strip() or None),
            recruiter_id=int(recruiter.id) if recruiter is not None else None,
            recruiter_name=(
                recruiter.name
                if recruiter is not None
                else (str(explicit.get("recruiter_name")).strip() or None)
            ),
            recruiter_tz=(
                recruiter.tz
                if recruiter is not None
                else (str(explicit.get("recruiter_tz")).strip() or None)
            ),
            source=source or BOOKING_CONTEXT_SOURCE_EXPLICIT,
            is_explicit=True,
        )

    city_id, city_name, source = await _booking_context_prefill(
        session,
        journey_session=journey_session,
        profile=profile,
    )
    return CandidateBookingContextEnvelope(
        profile=profile,
        journey_session=journey_session,
        city_id=city_id,
        city_name=city_name,
        recruiter_id=None,
        recruiter_name=None,
        recruiter_tz=None,
        source=source,
        is_explicit=False,
    )


async def _load_journey_session_for_update(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> CandidateJourneySession:
    journey_session = await session.scalar(
        select(CandidateJourneySession)
        .where(CandidateJourneySession.id == principal.journey_session_id)
        .with_for_update()
    )
    if journey_session is None or journey_session.candidate_id != principal.candidate_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")
    return journey_session


async def _load_test1_step_state(
    session: AsyncSession,
    journey_session_id: int,
    *,
    for_update: bool,
) -> CandidateJourneyStepState | None:
    return await _load_step_state(
        session,
        journey_session_id,
        step_key=TEST1_STEP_KEY,
        for_update=for_update,
    )


async def _load_step_state(
    session: AsyncSession,
    journey_session_id: int,
    *,
    step_key: str,
    for_update: bool,
) -> CandidateJourneyStepState | None:
    stmt = select(CandidateJourneyStepState).where(
        CandidateJourneyStepState.session_id == journey_session_id,
        CandidateJourneyStepState.step_key == step_key,
    )
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def _get_or_create_test1_step_state(
    session: AsyncSession,
    journey_session: CandidateJourneySession,
) -> CandidateJourneyStepState:
    step_state = await _load_test1_step_state(session, journey_session.id, for_update=True)
    if step_state is not None:
        return step_state
    step_state = CandidateJourneyStepState(
        session_id=journey_session.id,
        step_key=TEST1_STEP_KEY,
        step_type="form",
        status=CandidateJourneyStepStatus.IN_PROGRESS.value,
        payload_json=None,
    )
    session.add(step_state)
    await session.flush()
    return step_state


async def _get_or_create_step_state(
    session: AsyncSession,
    journey_session: CandidateJourneySession,
    *,
    step_key: str,
    step_type: str,
) -> CandidateJourneyStepState:
    step_state = await _load_step_state(
        session,
        journey_session.id,
        step_key=step_key,
        for_update=True,
    )
    if step_state is not None:
        return step_state
    step_state = CandidateJourneyStepState(
        session_id=journey_session.id,
        step_key=step_key,
        step_type=step_type,
        status=CandidateJourneyStepStatus.PENDING.value,
        payload_json=None,
    )
    session.add(step_state)
    await session.flush()
    return step_state


def _test2_payload(step_state: CandidateJourneyStepState | None) -> dict[str, Any]:
    payload = dict(getattr(step_state, "payload_json", None) or {})
    return dict(payload.get("candidate_access_test2") or {})


def _replace_test2_payload(
    step_state: CandidateJourneyStepState,
    test2_payload: dict[str, Any],
) -> None:
    payload = dict(step_state.payload_json or {})
    payload["candidate_access_test2"] = dict(test2_payload or {})
    step_state.payload_json = payload


def _test2_questions() -> list[dict[str, Any]]:
    refresh_questions_bank()
    return list(TEST2_QUESTIONS)


def _serialize_test2_attempts(raw_attempts: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in dict(raw_attempts or {}).items():
        normalized_key = str(key)
        attempt = dict(value or {})
        answers = []
        for answer in list(attempt.get("answers") or []):
            item = dict(answer or {})
            answers.append(
                {
                    "answer": int(item.get("answer")) if item.get("answer") is not None else None,
                    "time": str(item.get("time") or ""),
                    "overtime": bool(item.get("overtime")),
                }
            )
        result[normalized_key] = {
            "answers": answers,
            "is_correct": bool(attempt.get("is_correct")),
            "start_time": str(attempt.get("start_time") or "") or None,
        }
    return result


def _current_test2_question_index(
    *,
    attempts: dict[str, Any],
    questions: list[dict[str, Any]],
) -> int | None:
    for index in range(len(questions)):
        attempt = dict(attempts.get(str(index)) or {})
        if not bool(attempt.get("is_correct")):
            return index
    return None


def _test2_question_snapshot(question: dict[str, Any], *, index: int) -> dict[str, Any]:
    options = list(question.get("options") or [])
    return {
        "id": f"test2-{index}",
        "question_index": index,
        "prompt": str(question.get("text") or ""),
        "options": [
            {"label": str(option), "value": str(position)}
            for position, option in enumerate(options)
        ],
        "helper": None,
        "placeholder": None,
    }


async def _load_active_intro_day_slot(
    session: AsyncSession,
    candidate: User,
) -> Slot | None:
    booking_filters = _candidate_slot_filters(candidate)
    result = await session.execute(
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(
            or_(*booking_filters),
            func.lower(func.coalesce(Slot.purpose, "interview")) == "intro_day",
            func.lower(Slot.status).in_(list(ACTIVE_INTERVIEW_SLOT_STATUSES)),
        )
        .order_by(Slot.start_utc.asc(), Slot.id.asc())
        .limit(1)
    )
    slot = result.scalar_one_or_none()
    if slot is not None and slot.start_utc.tzinfo is None:
        slot.start_utc = slot.start_utc.replace(tzinfo=UTC)
    return slot


async def _latest_max_journey_session_for_candidate(
    session: AsyncSession,
    *,
    candidate_id: int,
) -> CandidateJourneySession | None:
    return await session.scalar(
        select(CandidateJourneySession)
        .where(CandidateJourneySession.candidate_id == candidate_id)
        .order_by(CandidateJourneySession.id.desc())
        .limit(1)
        .with_for_update()
    )


async def ensure_candidate_booking_allowed(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> None:
    journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
    if journey_session is None or journey_session.candidate_id != principal.candidate_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")

    if (
        NEXT_ACTION_SELECT_INTERVIEW_SLOT in _allowed_next_actions(journey_session)
        or journey_session.current_step_key == BOOKING_STEP_KEY
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Interview slot selection is not available until Test1 screening invites the candidate to interview.",
    )


async def load_candidate_profile(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> CandidateProfile:
    candidate = await session.get(User, principal.candidate_id)
    if candidate is None or not candidate.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    city_id = None
    city_name = None
    timezone_name = "Europe/Moscow"
    normalized_city = str(candidate.city or "").strip()
    if normalized_city:
        city = await session.scalar(select(City).where(City.name == normalized_city).limit(1))
        if city is None:
            city = await session.scalar(
                select(City).where(func.lower(City.name) == normalized_city.lower()).limit(1)
            )
        if city is not None:
            city_id = city.id
            city_name = city.name
            timezone_name = city.tz or timezone_name

    if candidate.manual_slot_timezone:
        timezone_name = candidate.manual_slot_timezone

    return CandidateProfile(
        candidate=candidate,
        city_id=city_id,
        city_name=city_name,
        timezone_name=timezone_name,
        telegram_ids=_known_telegram_ids(candidate),
    )


async def load_active_interview_booking(
    session: AsyncSession,
    candidate: User,
) -> Slot | None:
    booking_filters = _candidate_slot_filters(candidate)
    result = await session.execute(
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(
            or_(*booking_filters),
            func.lower(func.coalesce(Slot.purpose, "interview")) == "interview",
            func.lower(Slot.status).in_(list(ACTIVE_INTERVIEW_SLOT_STATUSES)),
        )
        .order_by(Slot.start_utc.asc(), Slot.id.asc())
        .limit(1)
    )
    slot = result.scalar_one_or_none()
    if slot is not None and slot.start_utc.tzinfo is None:
        slot.start_utc = slot.start_utc.replace(tzinfo=UTC)
    return slot


async def load_candidate_journey(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> CandidateJourneyEnvelope:
    profile = await load_candidate_profile(session, principal)
    journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
    if journey_session is None or journey_session.candidate_id != profile.candidate.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")

    active_booking = await load_active_interview_booking(session, profile.candidate)
    return CandidateJourneyEnvelope(
        profile=profile,
        journey_session=journey_session,
        active_booking=active_booking,
    )


async def mark_max_candidate_test2_ready(
    session: AsyncSession,
    *,
    candidate: User,
    slot_id: int | None,
    candidate_tz: str | None,
    candidate_city_id: int | None,
    candidate_name: str | None,
    required: bool,
) -> CandidateJourneySession | None:
    journey_session = await _latest_max_journey_session_for_candidate(
        session,
        candidate_id=int(candidate.id),
    )
    if journey_session is None:
        return None

    step_state = await _get_or_create_step_state(
        session,
        journey_session,
        step_key=TEST2_STEP_KEY,
        step_type="quiz",
    )
    test2_payload = _test2_payload(step_state)
    test2_payload.update(
        {
            "version": 1,
            "state": "ready",
            "questions_bank_version": get_questions_bank_version(),
            "attempts": dict(test2_payload.get("attempts") or {}),
            "slot_id": slot_id,
            "required": bool(required),
            "candidate_tz": str(candidate_tz or "") or None,
            "candidate_city_id": candidate_city_id,
            "candidate_name": str(candidate_name or candidate.fio or "").strip() or None,
            "invite_sent_at": datetime.now(UTC).isoformat(),
            "source": "max",
        }
    )
    _replace_test2_payload(step_state, test2_payload)
    step_state.status = CandidateJourneyStepStatus.PENDING.value
    step_state.completed_at = None
    journey_session.current_step_key = TEST2_STEP_KEY
    journey_session.last_activity_at = datetime.now(UTC)
    await session.flush()
    return journey_session


async def load_candidate_test2_state(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> CandidateTest2Envelope:
    profile = await load_candidate_profile(session, principal)
    journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
    if journey_session is None or journey_session.candidate_id != profile.candidate.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")

    step_state = await _load_step_state(
        session,
        journey_session.id,
        step_key=TEST2_STEP_KEY,
        for_update=True,
    )
    if step_state is None:
        if getattr(profile.candidate, "candidate_status", None) not in {
            CandidateStatus.TEST2_SENT,
            CandidateStatus.TEST2_COMPLETED,
            CandidateStatus.TEST2_FAILED,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Test2 is not available for this candidate-access session.",
            )
        step_state = await _get_or_create_step_state(
            session,
            journey_session,
            step_key=TEST2_STEP_KEY,
            step_type="quiz",
        )
        _replace_test2_payload(
            step_state,
            {
                "version": 1,
                "state": "ready",
                "questions_bank_version": get_questions_bank_version(),
                "attempts": {},
                "source": "max",
            },
        )
        step_state.status = CandidateJourneyStepStatus.PENDING.value
        await session.flush()

    questions = _test2_questions()
    payload = _test2_payload(step_state)
    attempts = _serialize_test2_attempts(payload.get("attempts"))
    current_question_index = _current_test2_question_index(
        attempts=attempts,
        questions=questions,
    )
    if current_question_index is not None:
        attempt = dict(attempts.get(str(current_question_index)) or {})
        if not attempt.get("start_time"):
            attempt["start_time"] = datetime.now(UTC).isoformat()
            attempts[str(current_question_index)] = attempt
            payload["attempts"] = attempts
            payload.setdefault("started_at", datetime.now(UTC).isoformat())
            payload["state"] = "in_progress"
            _replace_test2_payload(step_state, payload)
            step_state.status = CandidateJourneyStepStatus.IN_PROGRESS.value
            journey_session.current_step_key = TEST2_STEP_KEY
            journey_session.last_activity_at = datetime.now(UTC)
            await session.flush()

    result = dict(payload.get("result") or {})
    return CandidateTest2Envelope(
        profile=profile,
        journey_session=journey_session,
        questions=[_test2_question_snapshot(question, index=index) for index, question in enumerate(questions)],
        current_question_index=current_question_index,
        attempts=attempts,
        is_started=bool(payload.get("started_at")),
        is_completed=bool(result.get("completed")),
        score=float(result["score"]) if result.get("score") is not None else None,
        correct_answers=int(result["correct_answers"]) if result.get("correct_answers") is not None else None,
        total_questions=len(questions),
        passed=bool(result.get("passed")) if result.get("completed") else None,
        rating=str(result.get("rating") or "") or None,
        required_next_action=str(result.get("required_next_action") or "") or None,
        result_message=str(result.get("result_message") or "") or None,
    )


async def submit_candidate_test2_answer(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    question_index: int,
    answer_index: int,
) -> CandidateTest2Envelope:
    profile = await load_candidate_profile(session, principal)
    journey_session = await _load_journey_session_for_update(session, principal)
    step_state = await _get_or_create_step_state(
        session,
        journey_session,
        step_key=TEST2_STEP_KEY,
        step_type="quiz",
    )
    questions = _test2_questions()
    if question_index < 0 or question_index >= len(questions):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Test2 question index.")

    payload = _test2_payload(step_state)
    attempts = _serialize_test2_attempts(payload.get("attempts"))
    current_question_index = _current_test2_question_index(attempts=attempts, questions=questions)
    if current_question_index is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Test2 has already been completed.")
    if int(question_index) != int(current_question_index):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Answer the current Test2 question first.")

    question = questions[question_index]
    options = list(question.get("options") or [])
    if answer_index < 0 or answer_index >= len(options):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Test2 answer option.")

    now = datetime.now(UTC)
    attempt = dict(attempts.get(str(question_index)) or {})
    answers = list(attempt.get("answers") or [])
    start_time_raw = str(attempt.get("start_time") or "").strip()
    start_time = None
    if start_time_raw:
        try:
            start_time = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
        except ValueError:
            start_time = None
    if start_time is None:
        start_time = now
    overtime = int((now - start_time).total_seconds()) > TIME_LIMIT
    answers.append(
        {
            "answer": int(answer_index),
            "time": now.isoformat(),
            "overtime": overtime,
        }
    )
    attempt["answers"] = answers
    attempt["is_correct"] = int(answer_index) == int(question.get("correct"))
    attempt["start_time"] = start_time.isoformat()
    attempts[str(question_index)] = attempt
    payload["attempts"] = attempts
    payload.setdefault("started_at", now.isoformat())
    payload["state"] = "in_progress"
    _replace_test2_payload(step_state, payload)
    step_state.status = CandidateJourneyStepStatus.IN_PROGRESS.value
    journey_session.current_step_key = TEST2_STEP_KEY
    journey_session.last_activity_at = now

    next_index = _current_test2_question_index(attempts=attempts, questions=questions)
    if next_index is None:
        return await _finalize_candidate_test2(
            session,
            profile=profile,
            journey_session=journey_session,
            step_state=step_state,
            attempts=attempts,
            questions=questions,
        )

    next_attempt = dict(attempts.get(str(next_index)) or {})
    if not next_attempt.get("start_time"):
        next_attempt["start_time"] = now.isoformat()
        attempts[str(next_index)] = next_attempt
        payload["attempts"] = attempts
        _replace_test2_payload(step_state, payload)
    await session.flush()
    return await load_candidate_test2_state(session, principal)


async def _finalize_candidate_test2(
    session: AsyncSession,
    *,
    profile: CandidateProfile,
    journey_session: CandidateJourneySession,
    step_state: CandidateJourneyStepState,
    attempts: dict[str, Any],
    questions: list[dict[str, Any]],
) -> CandidateTest2Envelope:
    correct_answers = sum(1 for attempt in attempts.values() if bool(dict(attempt).get("is_correct")))
    score = calculate_score({int(key): dict(value) for key, value in attempts.items()})
    rating = get_rating(score)
    passed = (correct_answers / max(1, len(questions))) >= PASS_THRESHOLD
    result_message = (
        "Тест 2 завершён. Ожидайте приглашение на ознакомительный день."
        if passed
        else "Тест 2 завершён. Команда вернётся к вам с итоговым решением."
    )
    required_next_action = "wait_intro_day_invitation" if passed else "await_manual_review"
    question_data: list[dict[str, Any]] = []
    report_lines = [
        "📋 Отчёт по Тесту 2",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Дата: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}",
        f"Candidate ID: {profile.candidate.id}",
        f"ФИО: {profile.candidate.fio}",
        f"Город: {profile.candidate.city or '—'}",
        f"Баллы: {score} ({correct_answers}/{len(questions)} верных)",
        f"Рейтинг: {rating}",
        "",
        "Вопросы:",
    ]
    for index, question in enumerate(questions, start=1):
        options = list(question.get("options") or [])
        attempt = dict(attempts.get(str(index - 1)) or {})
        answers_seq = list(attempt.get("answers") or [])
        answers_count = len(answers_seq)
        user_answer_idx = answers_seq[-1].get("answer") if answers_seq else None
        user_answer_text = options[user_answer_idx] if isinstance(user_answer_idx, int) and 0 <= user_answer_idx < len(options) else "—"
        correct_idx = question.get("correct")
        correct_text = options[correct_idx] if isinstance(correct_idx, int) and 0 <= correct_idx < len(options) else "—"
        overtime = any(bool(entry.get("overtime")) for entry in answers_seq)
        question_data.append(
            {
                "question_index": index,
                "question_text": question.get("text", ""),
                "correct_answer": correct_text,
                "user_answer": user_answer_text,
                "attempts_count": answers_count,
                "time_spent": 0,
                "is_correct": bool(attempt.get("is_correct")),
                "overtime": overtime,
            }
        )
        report_lines.extend(
            [
                f"{index}. {question.get('text', '')}",
                f"   Ответ кандидата: {user_answer_text}",
                f"   Правильный ответ: {correct_text} {'✅' if attempt.get('is_correct') else '❌'}",
                f"   Попыток: {answers_count} · Просрочено: {'да' if overtime else 'нет'}",
                "",
            ]
        )

    await save_test_result(
        user_id=int(profile.candidate.id),
        raw_score=correct_answers,
        final_score=score,
        rating="TEST2",
        total_time=0,
        question_data=question_data,
        source="max",
    )
    report_dir = Path(REPORTS_DIR) / str(profile.candidate.id)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "test2.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    await update_candidate_reports(
        int(profile.candidate.id),
        test2_path=str(Path("reports") / str(profile.candidate.id) / "test2.txt"),
    )

    payload = _test2_payload(step_state)
    payload["attempts"] = attempts
    payload["state"] = "completed"
    payload["result"] = {
        "completed": True,
        "score": score,
        "correct_answers": correct_answers,
        "total_questions": len(questions),
        "passed": passed,
        "rating": rating,
        "required_next_action": required_next_action,
        "result_message": result_message,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    _replace_test2_payload(step_state, payload)
    step_state.status = CandidateJourneyStepStatus.COMPLETED.value
    step_state.completed_at = datetime.now(UTC)
    journey_session.current_step_key = INTRO_DAY_STEP_KEY if passed else TEST2_STEP_KEY
    journey_session.last_activity_at = datetime.now(UTC)

    target_status = CandidateStatus.TEST2_COMPLETED if passed else CandidateStatus.TEST2_FAILED
    await update_candidate_status_by_candidate_id(
        profile.candidate.candidate_id,
        target_status,
        force=bool(passed),
        session=session,
    )
    try:
        await analytics.log_funnel_event(
            analytics.FunnelEvent.TEST2_COMPLETED,
            user_id=int(profile.candidate.id),
            candidate_id=int(profile.candidate.id),
            metadata={
                "channel": "max",
                "result": "passed" if passed else "failed",
                "score": score,
                "correct": correct_answers,
                "total": len(questions),
            },
            session=session,
        )
    except Exception:
        logger.exception("Failed to log MAX TEST2_COMPLETED for candidate %s", profile.candidate.id)

    await session.flush()
    return CandidateTest2Envelope(
        profile=profile,
        journey_session=journey_session,
        questions=[_test2_question_snapshot(question, index=index) for index, question in enumerate(questions)],
        current_question_index=None,
        attempts=attempts,
        is_started=True,
        is_completed=True,
        score=score,
        correct_answers=correct_answers,
        total_questions=len(questions),
        passed=passed,
        rating=rating,
        required_next_action=required_next_action,
        result_message=result_message,
    )


async def load_candidate_intro_day(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> CandidateIntroDayEnvelope:
    profile = await load_candidate_profile(session, principal)
    journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
    if journey_session is None or journey_session.candidate_id != profile.candidate.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")
    slot = await _load_active_intro_day_slot(session, profile.candidate)
    if slot is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Intro day details are not available yet.")
    city = getattr(slot, "city", None)
    return CandidateIntroDayEnvelope(
        profile=profile,
        journey_session=journey_session,
        slot=slot,
        city_name=getattr(city, "name_plain", None) or getattr(city, "name", None),
        intro_address=str(getattr(slot, "intro_address", None) or getattr(city, "intro_address", None) or "").strip() or None,
        intro_contact=str(getattr(slot, "intro_contact", None) or "").strip() or None,
        contact_name=str(getattr(city, "contact_name", None) or "").strip() or None,
        contact_phone=str(getattr(city, "contact_phone", None) or "").strip() or None,
        recruiter_name=getattr(getattr(slot, "recruiter", None), "name", None),
        confirm_state=(slot.status or "").lower(),
    )


async def confirm_candidate_intro_day(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> CandidateIntroDayEnvelope:
    envelope = await load_candidate_intro_day(session, principal)
    if envelope.slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intro day slot not found")
    from backend.domain.repositories import confirm_slot_by_candidate

    result = await confirm_slot_by_candidate(
        int(envelope.slot.id),
        session=session,
        update_candidate_status=True,
    )
    if result.slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intro day slot not found")
    journey_session = await _load_journey_session_for_update(session, principal)
    journey_session.current_step_key = INTRO_DAY_STEP_KEY
    journey_session.last_activity_at = datetime.now(UTC)
    await session.flush()
    return await load_candidate_intro_day(session, principal)


async def _append_candidate_journey_event(
    session: AsyncSession,
    *,
    candidate_id: int,
    event_key: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> None:
    event = CandidateJourneyEvent(
        candidate_id=int(candidate_id),
        event_key=event_key,
        stage="screening",
        status_slug=None,
        actor_type="candidate_access",
        actor_id=None,
        summary=summary,
        payload_json=dict(payload or {}),
    )
    session.add(event)
    await session.flush()


def _clean_text(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _format_manual_availability_window(
    *,
    window_start: datetime | None,
    window_end: datetime | None,
    timezone_label: str | None,
) -> str | None:
    if window_start is None and window_end is None:
        return None
    try:
        zone = ZoneInfo(str(timezone_label or "Europe/Moscow"))
    except Exception:
        zone = ZoneInfo("Europe/Moscow")
    if window_start is not None:
        window_start = window_start.astimezone(zone)
    if window_end is not None:
        window_end = window_end.astimezone(zone)
    if window_start is not None and window_end is not None:
        if window_start.date() == window_end.date():
            return (
                f"{window_start.strftime('%d.%m %H:%M')}"
                f"–{window_end.strftime('%H:%M')} ({zone.key})"
            )
        return (
            f"{window_start.strftime('%d.%m %H:%M')}"
            f" – {window_end.strftime('%d.%m %H:%M')} ({zone.key})"
        )
    single = window_start or window_end
    if single is None:
        return None
    return f"{single.strftime('%d.%m %H:%M')} ({zone.key})"


def _sync_candidate_profile_from_test1_state(
    candidate: User,
    *,
    answers: dict[str, str] | None,
    city_name: str | None,
) -> None:
    fio = _clean_text((answers or {}).get("fio"))
    if fio:
        candidate.fio = fio
    normalized_city = _clean_text(city_name) or _clean_text((answers or {}).get("city"))
    if normalized_city:
        candidate.city = normalized_city
    candidate.last_activity = datetime.now(UTC)


async def _activate_max_intake_candidate(
    session: AsyncSession,
    *,
    candidate: User,
    event_key: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    if str(getattr(candidate, "lifecycle_state", "") or "").strip().lower() != LIFECYCLE_DRAFT:
        return False
    candidate.lifecycle_state = "active"
    await _append_candidate_journey_event(
        session,
        candidate_id=int(candidate.id),
        event_key=event_key,
        summary=summary,
        payload=payload,
    )
    await session.flush()
    return True


async def _load_active_applications_for_candidate(
    session: AsyncSession,
    *,
    candidate_id: int,
) -> list[Application]:
    result = await session.execute(
        select(Application)
        .where(
            Application.candidate_id == int(candidate_id),
            Application.archived_at.is_(None),
        )
        .order_by(Application.created_at.desc(), Application.id.desc())
    )
    return list(result.scalars().all())


async def bind_max_candidate_by_phone(
    session: AsyncSession,
    *,
    provider_user_id: str,
    phone: str,
    source: str = "max_global_link",
) -> CandidateContactBindEnvelope:
    normalized_phone = normalize_candidate_phone(phone)
    if not normalized_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите телефон в формате +7XXXXXXXXXX.",
        )

    candidate_rows = (
        await session.execute(
            select(User)
            .where(
                User.phone_normalized == normalized_phone,
                User.is_active.is_(True),
            )
            .order_by(User.id.desc())
            .limit(2)
        )
    ).scalars().all()

    if not candidate_rows:
        return CandidateContactBindEnvelope(
            status="manual_review_required",
            message=(
                "Мы не нашли единственную активную анкету по этому номеру. "
                "Откройте чат MAX или дождитесь сообщения от рекрутера."
            ),
        )

    if len(candidate_rows) > 1:
        return CandidateContactBindEnvelope(
            status="manual_review_required",
            message=(
                "По номеру найдено несколько анкет. Продолжим после ручной проверки рекрутера."
            ),
        )

    candidate = candidate_rows[0]
    if candidate.max_user_id and str(candidate.max_user_id).strip() != provider_user_id:
        await _append_candidate_journey_event(
            session,
            candidate_id=int(candidate.id),
            event_key="max_global_link_manual_review_required",
            summary="MAX global link requires manual review before candidate binding.",
            payload={
                "reason": "identity_mismatch",
                "source": source,
            },
        )
        return CandidateContactBindEnvelope(
            status="manual_review_required",
            message=(
                "Эта анкета уже связана с другим MAX-профилем. Продолжим после ручной проверки."
            ),
            candidate=candidate,
        )

    applications = await _load_active_applications_for_candidate(
        session,
        candidate_id=int(candidate.id),
    )
    if len(applications) != 1:
        await _append_candidate_journey_event(
            session,
            candidate_id=int(candidate.id),
            event_key="max_global_link_manual_review_required",
            summary="MAX global link requires manual review before launch context can be restored.",
            payload={
                "reason": "application_context_ambiguous",
                "active_application_count": len(applications),
                "source": source,
            },
        )
        return CandidateContactBindEnvelope(
            status="manual_review_required",
            message=(
                "Мы нашли анкету, но не смогли безопасно восстановить шаг кандидата автоматически. "
                "Рекрутер продолжит вручную."
            ),
            candidate=candidate,
        )

    candidate.max_user_id = provider_user_id
    candidate.messenger_platform = "max"
    candidate.source = candidate.source or "max"

    preview = await create_max_launch_invite(
        int(candidate.id),
        int(applications[0].id),
        session=session,
        issued_by_type="candidate_self_serve",
        issued_by_id=provider_user_id,
    )
    await _append_candidate_journey_event(
        session,
        candidate_id=int(candidate.id),
        event_key="max_global_link_bound",
        summary="MAX global link restored candidate access after exact phone match.",
        payload={
            "application_id": int(applications[0].id),
            "start_param": preview.start_param,
            "source": source,
        },
    )

    return CandidateContactBindEnvelope(
        status="bound",
        message="Анкета найдена. Продолжаем путь кандидата в mini app.",
        candidate=candidate,
        application_id=int(applications[0].id),
        start_param=preview.start_param,
        expires_at=preview.expires_at,
    )


async def load_candidate_test1_state(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> CandidateTest1Envelope:
    profile = await load_candidate_profile(session, principal)
    journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
    if journey_session is None or journey_session.candidate_id != profile.candidate.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")

    step_state = await _load_test1_step_state(session, journey_session.id, for_update=False)
    payload = dict(step_state.payload_json or {}) if step_state is not None else {}
    draft = dict(payload.get("draft") or {})
    completion = _extract_completion_payload(step_state)
    questions = await materialize_test1_questions(draft.get("answers") or {})

    return CandidateTest1Envelope(
        profile=profile,
        journey_session=journey_session,
        questions=questions,
        draft_answers={str(key): str(value) for key, value in dict(draft.get("answers") or {}).items()},
        is_completed=bool(completion),
        screening_decision=completion.get("screening_decision") if completion else None,
        interview_offer=completion.get("interview_offer") if completion else None,
        required_next_action=completion.get("required_next_action") if completion else None,
    )


async def save_candidate_test1_answers(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    answers: dict[str, str],
) -> CandidateTest1Envelope:
    if not answers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Test1 answers were provided.")

    profile = await load_candidate_profile(session, principal)
    journey_session = await _load_journey_session_for_update(session, principal)
    step_state = await _get_or_create_test1_step_state(session, journey_session)
    if _extract_completion_payload(step_state):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Test1 has already been completed for this candidate-access session.",
        )

    payload = dict(step_state.payload_json or {})
    draft = dict(payload.get("draft") or {})
    try:
        merged_state = await merge_test1_answers(
            existing_answers=draft.get("answers") or {},
            existing_payload=draft.get("payload") or {},
            existing_city_id=draft.get("city_id") or profile.city_id,
            existing_city_name=draft.get("city_name") or profile.city_name,
            existing_candidate_tz=draft.get("candidate_tz") or profile.timezone_name,
            submitted_answers=answers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _sync_candidate_profile_from_test1_state(
        profile.candidate,
        answers=merged_state.answers,
        city_name=merged_state.city_name,
    )
    step_state.payload_json = {
        **payload,
        **serialize_step_payload(
            draft_state=merged_state,
            source="candidate_access",
            surface=principal.surface,
        ),
    }
    step_state.status = CandidateJourneyStepStatus.IN_PROGRESS.value
    step_state.completed_at = None
    journey_session.current_step_key = TEST1_STEP_KEY
    journey_session.last_activity_at = datetime.now(UTC)
    await session.flush()

    questions = await materialize_test1_questions(merged_state.answers)
    refreshed_profile = await load_candidate_profile(session, principal)
    return CandidateTest1Envelope(
        profile=refreshed_profile,
        journey_session=journey_session,
        questions=questions,
        draft_answers=merged_state.answers,
        is_completed=False,
        screening_decision=None,
        interview_offer=None,
        required_next_action=None,
    )


async def complete_candidate_test1(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> CandidateTest1Envelope:
    profile = await load_candidate_profile(session, principal)
    journey_session = await _load_journey_session_for_update(session, principal)
    step_state = await _get_or_create_test1_step_state(session, journey_session)
    candidate = await session.scalar(
        select(User).where(User.id == profile.candidate.id).with_for_update()
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    draft_payload = dict(step_state.payload_json or {})
    draft_state = dict(draft_payload.get("draft") or {})
    _sync_candidate_profile_from_test1_state(
        candidate,
        answers={str(key): str(value) for key, value in dict(draft_state.get("answers") or {}).items()},
        city_name=_clean_text(draft_state.get("city_name")),
    )
    try:
        completion = await complete_test1_for_candidate(
            session=session,
            candidate=candidate,
            journey_session=journey_session,
            step_state=step_state,
            source="candidate_access",
            channel="max",
            surface=principal.surface,
            actor_type="candidate_access_session",
            actor_id=str(principal.access_session_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if str(completion.required_next_action or "").strip() != NEXT_ACTION_SELECT_INTERVIEW_SLOT:
        await _activate_max_intake_candidate(
            session,
            candidate=candidate,
            event_key="max_intake_activated",
            summary="MAX draft intake became visible after Test1 completion.",
            payload={
                "activation_source": "test1_complete",
                "required_next_action": completion.required_next_action,
            },
        )

    payload = dict(step_state.payload_json or {})
    draft = dict(payload.get("draft") or {})
    questions = await materialize_test1_questions(draft.get("answers") or {})
    refreshed_profile = await load_candidate_profile(session, principal)

    return CandidateTest1Envelope(
        profile=refreshed_profile,
        journey_session=journey_session,
        questions=questions,
        draft_answers={str(key): str(value) for key, value in dict(draft.get("answers") or {}).items()},
        is_completed=completion.is_completed,
        screening_decision=completion.screening_decision,
        interview_offer=completion.interview_offer,
        required_next_action=completion.required_next_action,
    )


async def list_candidate_booking_cities(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> list[CandidateBookingCity]:
    del session
    del principal
    cities = await get_candidate_cities()
    result: list[CandidateBookingCity] = []
    for city in cities:
        recruiters = await get_active_recruiters_for_city(int(city.id))
        summary = await get_recruiters_free_slots_summary((int(item.id) for item in recruiters), city_id=int(city.id))
        available_recruiters = len(summary)
        available_slots = sum(int(total) for _, total in summary.values())
        result.append(
            CandidateBookingCity(
                city_id=int(city.id),
                city_name=city.name_plain,
                timezone_name=city.tz or "Europe/Moscow",
                has_available_recruiters=available_recruiters > 0,
                available_recruiters=available_recruiters,
                available_slots=available_slots,
            )
        )
    return result


async def list_candidate_booking_recruiters(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    city_id: int,
) -> list[CandidateBookingRecruiter]:
    del session
    del principal
    recruiters = await get_active_recruiters_for_city(int(city_id))
    summary = await get_recruiters_free_slots_summary((int(item.id) for item in recruiters), city_id=int(city_id))
    items: list[CandidateBookingRecruiter] = []
    for recruiter in recruiters:
        info = summary.get(int(recruiter.id))
        if info is None:
            continue
        next_slot_utc, available_slots = info
        items.append(
            CandidateBookingRecruiter(
                recruiter_id=int(recruiter.id),
                recruiter_name=recruiter.name,
                timezone_name=recruiter.tz or "Europe/Moscow",
                available_slots=int(available_slots),
                next_slot_utc=next_slot_utc,
                city_id=int(city_id),
            )
        )
    items.sort(key=lambda item: (item.next_slot_utc or datetime.max.replace(tzinfo=UTC), item.recruiter_name.lower()))
    return items


async def save_candidate_booking_context(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    city_id: int,
    recruiter_id: int | None,
) -> CandidateBookingContextEnvelope:
    profile = await load_candidate_profile(session, principal)
    journey_session = await _load_journey_session_for_update(session, principal)
    city = await _load_city(session, city_id)
    if city is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="City not found")

    recruiter_name: str | None = None
    recruiter_tz: str | None = None
    if recruiter_id is not None:
        recruiters = await list_candidate_booking_recruiters(
            session,
            principal,
            city_id=int(city.id),
        )
        matched = next((item for item in recruiters if int(item.recruiter_id) == int(recruiter_id)), None)
        if matched is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Recruiter is not available for the selected city.",
            )
        recruiter_name = matched.recruiter_name
        recruiter_tz = matched.timezone_name

    _persist_booking_context(
        journey_session,
        city_id=int(city.id),
        city_name=city.name_plain,
        recruiter_id=int(recruiter_id) if recruiter_id is not None else None,
        recruiter_name=recruiter_name,
        recruiter_tz=recruiter_tz,
        source=BOOKING_CONTEXT_SOURCE_EXPLICIT,
    )
    journey_session.last_activity_at = datetime.now(UTC)
    await session.flush()
    return CandidateBookingContextEnvelope(
        profile=profile,
        journey_session=journey_session,
        city_id=int(city.id),
        city_name=city.name_plain,
        recruiter_id=int(recruiter_id) if recruiter_id is not None else None,
        recruiter_name=recruiter_name,
        recruiter_tz=recruiter_tz,
        source=BOOKING_CONTEXT_SOURCE_EXPLICIT,
        is_explicit=True,
    )


async def list_available_interview_slots(
    session: AsyncSession,
    *,
    city_id: int | None,
    recruiter_id: int | None = None,
    from_date: datetime | None,
    to_date: datetime | None,
) -> list[Slot]:
    if from_date is None:
        from_date = datetime.now(UTC)
    if to_date is None:
        to_date = from_date + timedelta(days=14)

    stmt = (
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(
            func.lower(func.coalesce(Slot.status, SlotStatus.FREE)) == SlotStatus.FREE,
            Slot.candidate_id.is_(None),
            Slot.candidate_tg_id.is_(None),
            func.lower(func.coalesce(Slot.purpose, "interview")) == "interview",
            Slot.start_utc >= from_date,
            Slot.start_utc <= to_date,
        )
        .order_by(Slot.start_utc.asc())
        .limit(100)
    )
    if city_id is not None:
        stmt = stmt.where(Slot.city_id == city_id)
    if recruiter_id is not None:
        stmt = stmt.where(Slot.recruiter_id == recruiter_id)
    result = await session.execute(stmt)
    return list(result.scalars())


async def save_candidate_manual_availability(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    note: str | None,
    window_start: datetime | None,
    window_end: datetime | None,
    timezone_label: str | None,
) -> CandidateManualAvailabilityEnvelope:
    await ensure_candidate_booking_allowed(session, principal)
    profile = await load_candidate_profile(session, principal)
    candidate = await session.scalar(
        select(User).where(User.id == profile.candidate.id).with_for_update()
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    note_value = _clean_text(note)
    timezone_value = _clean_text(timezone_label) or profile.timezone_name
    if note_value is None and window_start is None and window_end is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Опишите удобное время или укажите окно доступности.",
        )

    booking_context = await load_candidate_booking_context(session, principal)
    city_id = booking_context.city_id or profile.city_id
    city_name = booking_context.city_name or profile.city_name or candidate.city
    if city_id is None or not _clean_text(city_name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Choose a city before sending preferred interview time.",
        )
    candidate.city = str(city_name)

    journey_session = await _load_journey_session_for_update(session, principal)
    await save_manual_slot_response_for_user(
        session,
        candidate,
        window_start=window_start,
        window_end=window_end,
        note=note_value,
        timezone_label=timezone_value,
    )
    journey_session.last_activity_at = datetime.now(UTC)

    recruiters_notified = False
    try:
        recruiters_notified = await notify_recruiters_manual_availability(
            candidate_tg_id=candidate.telegram_id,
            candidate_name=candidate.fio,
            city_name=str(city_name),
            city_id=int(city_id),
            availability_window=_format_manual_availability_window(
                window_start=window_start,
                window_end=window_end,
                timezone_label=timezone_value,
            ),
            availability_note=note_value or "Кандидат указал предпочтения в mini app.",
            candidate_db_id=int(candidate.id),
            responsible_recruiter_id=candidate.responsible_recruiter_id,
            source_channel="max",
            candidate_external_id=_clean_text(candidate.max_user_id),
        )
    except Exception:
        recruiters_notified = False

    await _activate_max_intake_candidate(
        session,
        candidate=candidate,
        event_key="max_intake_activated",
        summary="MAX draft intake became visible after manual availability submission.",
        payload={
            "activation_source": "manual_availability",
            "city_id": int(city_id),
        },
    )
    await _append_candidate_journey_event(
        session,
        candidate_id=int(candidate.id),
        event_key="manual_slot_availability_submitted",
        summary="Candidate submitted preferred interview time in MAX mini app.",
        payload={
            "city_id": int(city_id),
            "city_name": str(city_name),
            "timezone_label": timezone_value,
            "has_window": bool(window_start or window_end),
            "recruiters_notified": recruiters_notified,
        },
    )
    logger.info(
        "candidate_access.manual_availability_submitted",
        extra={
            "candidate_id": int(candidate.id),
            "city_id": int(city_id),
            "has_window": bool(window_start or window_end),
            "recruiters_notified": recruiters_notified,
        },
    )
    await session.flush()
    return CandidateManualAvailabilityEnvelope(
        status="submitted",
        message="Пожелания по времени отправлены. Рекрутер подберёт слот и свяжется с вами.",
        recruiters_notified=recruiters_notified,
    )


async def create_candidate_booking(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    slot_id: int,
) -> tuple[User, Slot]:
    await ensure_candidate_booking_allowed(session, principal)
    profile = await load_candidate_profile(session, principal)
    await ensure_candidate_slot_write_allowed(session, profile.candidate)
    booking_context = await load_candidate_booking_context(session, principal)
    if booking_context.city_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Choose a city before selecting an interview slot.",
        )

    reservation = await reserve_domain_slot(
        slot_id,
        profile.telegram_ids[0] if profile.telegram_ids else None,
        profile.candidate.fio,
        profile.timezone_name,
        candidate_id=profile.candidate.candidate_id,
        candidate_city_id=booking_context.city_id,
        candidate_username=profile.candidate.username,
        purpose="interview",
        expected_recruiter_id=booking_context.recruiter_id,
        expected_city_id=booking_context.city_id,
    )
    if reservation.status != "reserved" or reservation.slot is None:
        raise _booking_conflict_error(reservation.status)
    slot = await session.scalar(
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(Slot.id == reservation.slot.id)
        .with_for_update()
    )
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booked slot not found")

    city_name = getattr(getattr(slot, "city", None), "name_plain", None) or booking_context.city_name
    profile.candidate.city = city_name or profile.candidate.city
    profile.candidate.responsible_recruiter_id = int(slot.recruiter_id)
    journey_session = await _load_journey_session_for_update(session, principal)
    _persist_booking_context(
        journey_session,
        city_id=int(slot.city_id) if slot.city_id is not None else booking_context.city_id,
        city_name=city_name,
        recruiter_id=int(slot.recruiter_id),
        recruiter_name=getattr(getattr(slot, "recruiter", None), "name", None),
        recruiter_tz=getattr(getattr(slot, "recruiter", None), "tz", None),
        source=BOOKING_CONTEXT_SOURCE_EXPLICIT,
    )
    journey_session.last_activity_at = datetime.now(UTC)
    await _activate_max_intake_candidate(
        session,
        candidate=profile.candidate,
        event_key="max_intake_activated",
        summary="MAX draft intake became visible after interview slot booking.",
        payload={
            "activation_source": "booking_created",
            "slot_id": int(slot.id),
        },
    )
    await session.flush()
    return profile.candidate, slot


async def load_owned_booking_for_update(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    booking_id: int,
) -> tuple[CandidateProfile, Slot]:
    profile = await load_candidate_profile(session, principal)
    ownership_filters = _candidate_slot_filters(profile.candidate)
    result = await session.execute(
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(Slot.id == booking_id, or_(*ownership_filters))
        .with_for_update()
    )
    slot = result.scalar_one_or_none()
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or does not belong to you",
        )
    purpose = (slot.purpose or "interview").strip().lower()
    if purpose != "interview":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate-access booking flow supports interview slots only.",
        )
    return profile, slot


async def confirm_candidate_booking(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    booking_id: int,
) -> Slot:
    profile, slot = await load_owned_booking_for_update(session, principal, booking_id)
    await ensure_candidate_slot_write_allowed(session, profile.candidate)
    result = await confirm_slot_by_candidate(
        booking_id,
        session=session,
        update_candidate_status=True,
    )
    if result.slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if result.status == "invalid_status":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking cannot be confirmed in its current status.",
        )
    return result.slot


async def cancel_candidate_booking(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    booking_id: int,
) -> None:
    profile, slot = await load_owned_booking_for_update(session, principal, booking_id)
    await ensure_candidate_slot_write_allowed(session, profile.candidate)
    try:
        enforce_slot_transition(slot.status, SlotStatus.FREE)
    except SlotStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await reject_slot(
        booking_id,
        session=session,
        update_candidate_status=True,
    )


async def reschedule_candidate_booking(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    booking_id: int,
    new_slot_id: int,
) -> tuple[User, Slot]:
    profile, old_slot = await load_owned_booking_for_update(session, principal, booking_id)
    await ensure_candidate_slot_write_allowed(session, profile.candidate)
    booking_context = await load_candidate_booking_context(session, principal)
    if booking_context.city_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Choose a city before selecting another interview slot.",
        )

    if booking_id == new_slot_id:
        return profile.candidate, old_slot

    try:
        enforce_slot_transition(old_slot.status, SlotStatus.FREE)
    except SlotStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    new_slot = await session.scalar(
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(Slot.id == new_slot_id)
        .with_for_update()
    )
    if new_slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="New slot not found")
    if booking_context.city_id is not None and int(new_slot.city_id or 0) != int(booking_context.city_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="New slot does not match the selected city.",
        )
    if booking_context.recruiter_id is not None and int(new_slot.recruiter_id) != int(booking_context.recruiter_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="New slot does not match the selected recruiter.",
        )

    new_slot_status = (new_slot.status or "").lower()
    if (
        (new_slot.candidate_id == profile.candidate.candidate_id)
        or (new_slot.candidate_tg_id is not None and new_slot.candidate_tg_id in profile.telegram_ids)
    ) and new_slot_status in {
        SlotStatus.PENDING,
        SlotStatus.BOOKED,
        SlotStatus.CONFIRMED,
        SlotStatus.CONFIRMED_BY_CANDIDATE,
    }:
        return profile.candidate, new_slot

    try:
        new_status = enforce_slot_transition(new_slot_status, SlotStatus.PENDING)
    except SlotStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    now_utc = datetime.now(UTC)
    new_slot.status = new_status
    new_slot.candidate_id = profile.candidate.candidate_id
    new_slot.candidate_tg_id = profile.telegram_ids[0] if profile.telegram_ids else None
    new_slot.candidate_city_id = profile.city_id or new_slot.city_id
    new_slot.candidate_fio = profile.candidate.fio
    new_slot.candidate_tz = profile.timezone_name
    new_slot.purpose = "interview"
    new_slot.updated_at = now_utc

    old_slot.status = SlotStatus.FREE
    old_slot.candidate_id = None
    old_slot.candidate_tg_id = None
    old_slot.candidate_city_id = None
    old_slot.candidate_fio = None
    old_slot.candidate_tz = None
    old_slot.purpose = "interview"
    old_slot.updated_at = now_utc

    await session.flush()
    profile.candidate.city = getattr(getattr(new_slot, "city", None), "name_plain", None) or profile.candidate.city
    profile.candidate.responsible_recruiter_id = int(new_slot.recruiter_id)
    journey_session = await _load_journey_session_for_update(session, principal)
    _persist_booking_context(
        journey_session,
        city_id=int(new_slot.city_id) if new_slot.city_id is not None else booking_context.city_id,
        city_name=getattr(getattr(new_slot, "city", None), "name_plain", None) or booking_context.city_name,
        recruiter_id=int(new_slot.recruiter_id),
        recruiter_name=getattr(getattr(new_slot, "recruiter", None), "name", None),
        recruiter_tz=getattr(getattr(new_slot, "recruiter", None), "tz", None),
        source=BOOKING_CONTEXT_SOURCE_EXPLICIT,
    )
    journey_session.last_activity_at = datetime.now(UTC)
    await session.flush()
    return profile.candidate, new_slot


def slot_duration_minutes(slot: Slot) -> int:
    return int(getattr(slot, "duration_min", DEFAULT_INTERVIEW_DURATION_MIN) or DEFAULT_INTERVIEW_DURATION_MIN)


__all__ = [
    "CandidateBookingCity",
    "CandidateBookingContextEnvelope",
    "CandidateContactBindEnvelope",
    "CandidateBookingRecruiter",
    "CandidateJourneyEnvelope",
    "CandidateTest1Envelope",
    "CandidateProfile",
    "bind_max_candidate_by_phone",
    "cancel_candidate_booking",
    "complete_candidate_test1",
    "confirm_candidate_booking",
    "create_candidate_booking",
    "ensure_candidate_booking_allowed",
    "ensure_candidate_slot_write_allowed",
    "list_candidate_booking_cities",
    "list_candidate_booking_recruiters",
    "list_available_interview_slots",
    "load_candidate_booking_context",
    "load_candidate_journey",
    "load_candidate_profile",
    "load_candidate_test1_state",
    "load_active_interview_booking",
    "reschedule_candidate_booking",
    "save_candidate_test1_answers",
    "save_candidate_booking_context",
    "slot_duration_minutes",
]
