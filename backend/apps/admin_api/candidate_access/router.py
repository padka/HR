"""Shared candidate-access API for external candidate surfaces."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.admin_api.candidate_access.auth import (
    CandidateAccessPrincipal,
    get_max_candidate_access_principal,
)
from backend.apps.admin_api.candidate_access.services import (
    CandidateBookingCity,
    CandidateBookingContextEnvelope,
    CandidateBookingRecruiter,
    CandidateContactBindEnvelope,
    CandidateIntroDayEnvelope,
    CandidateManualAvailabilityEnvelope,
    CandidateTest1Envelope,
    CandidateTest2Envelope,
    bind_max_candidate_by_phone,
    cancel_candidate_booking,
    complete_candidate_test1,
    confirm_candidate_booking,
    confirm_candidate_intro_day,
    create_candidate_booking,
    ensure_candidate_booking_allowed,
    list_available_interview_slots,
    list_candidate_booking_cities,
    list_candidate_booking_recruiters,
    load_candidate_booking_context,
    load_candidate_intro_day,
    load_candidate_journey,
    load_candidate_profile,
    load_candidate_test1_state,
    load_candidate_test2_state,
    reschedule_candidate_booking,
    save_candidate_booking_context,
    save_candidate_manual_availability,
    save_candidate_test1_answers,
    submit_candidate_test2_answer,
    slot_duration_minutes,
)
from backend.apps.admin_api.max_auth import validate_max_init_data
from backend.apps.admin_api.max_candidate_chat import (
    activate_max_chat_handoff,
    send_max_chat_prompt,
)
from backend.core.dependencies import get_async_session
from backend.core.settings import Settings, get_settings

router = APIRouter(tags=["candidate-access"])


class CandidateInfo(BaseModel):
    user_id: int
    full_name: str
    username: str | None = None
    candidate_id: int | None = None
    city_id: int | None = None
    city_name: str | None = None
    status: str | None = None


class SlotInfo(BaseModel):
    slot_id: int
    recruiter_id: int
    recruiter_name: str
    recruiter_tz: str | None = None
    start_utc: datetime
    end_utc: datetime
    duration_minutes: int
    is_available: bool
    city_id: int | None
    city_name: str | None = None


class BookingInfo(BaseModel):
    booking_id: int
    slot_id: int
    candidate_id: int
    recruiter_name: str
    start_utc: datetime
    end_utc: datetime
    status: str
    meet_link: str | None = None
    address: str | None = None


class CreateBookingRequest(BaseModel):
    slot_id: int = Field(..., gt=0)


class RescheduleBookingRequest(BaseModel):
    new_slot_id: int = Field(..., gt=0)


class CancelBookingRequest(BaseModel):
    reason: str | None = Field(None, max_length=500)


class JourneySessionInfo(BaseModel):
    journey_key: str
    journey_version: str
    current_step_key: str
    status: str
    application_id: int | None
    last_surface: str | None
    last_auth_method: str | None
    session_version: int


class CandidateJourneyResponse(BaseModel):
    candidate: CandidateInfo
    session: JourneySessionInfo
    active_booking: BookingInfo | None = None
    timeline: list[CandidateJourneyTimelineStep] = Field(default_factory=list)
    primary_action: CandidateJourneyPrimaryAction | None = None
    status_card: CandidateJourneyStatusCard | None = None
    prep_card: CandidateJourneyContentCard | None = None
    company_card: CandidateJourneyContentCard | None = None
    help_card: CandidateJourneyContentCard | None = None
    screening_decision: CandidateTest1Decision | None = None


class CandidateJourneyTimelineStep(BaseModel):
    key: str
    label: str
    state: str
    state_label: str
    detail: str | None = None


class CandidateJourneyPrimaryAction(BaseModel):
    key: str
    label: str
    kind: str
    detail: str | None = None


class CandidateJourneyStatusCard(BaseModel):
    title: str
    body: str
    tone: str


class CandidateJourneyContentCard(BaseModel):
    title: str
    body: str
    tone: str = "neutral"


class CandidateContactBindRequest(BaseModel):
    phone: str | None = Field(default=None, max_length=32)
    contact: dict[str, Any] | None = None


class CandidateContactBindResponse(BaseModel):
    status: str
    message: str
    start_param: str | None = None
    application_id: int | None = None
    expires_at: datetime | None = None


class CandidateManualAvailabilityRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
    window_start: datetime | None = None
    window_end: datetime | None = None
    timezone_label: str | None = Field(default=None, max_length=64)


class CandidateManualAvailabilityResponse(BaseModel):
    status: str
    message: str
    recruiters_notified: bool


class CandidateIntroDayResponse(BaseModel):
    booking_id: int
    city_name: str | None = None
    recruiter_name: str | None = None
    start_utc: datetime
    end_utc: datetime
    address: str | None = None
    intro_contact: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    status: str


def _validated_max_init_data(
    *,
    init_data: str,
    settings: Settings,
):
    if not getattr(settings, "max_adapter_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MAX adapter is disabled.",
        )
    max_bot_token = str(getattr(settings, "max_bot_token", "") or "").strip()
    if not max_bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX bot token is not configured.",
        )
    try:
        return validate_max_init_data(
            init_data,
            max_bot_token,
            max_age_seconds=int(getattr(settings, "max_init_data_max_age_seconds", 86400)),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid MAX initData: {exc}",
        ) from exc


class Test1QuestionOption(BaseModel):
    label: str
    value: str
    city_id: int | None = None
    tz: str | None = None


class Test1Question(BaseModel):
    id: str
    prompt: str
    placeholder: str | None = None
    helper: str | None = None
    question_index: int
    options: list[Test1QuestionOption] = Field(default_factory=list)


class CandidateTest1Decision(BaseModel):
    outcome: str
    reason_code: str
    explanation: str
    strictness: str
    required_next_action: str


class CandidateTest1Response(BaseModel):
    journey_step: str
    questions: list[Test1Question]
    draft_answers: dict[str, str]
    is_completed: bool
    screening_decision: CandidateTest1Decision | None = None
    interview_offer: dict[str, Any] | None = None
    required_next_action: str | None = None


class CandidateTest1AnswersRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class Test2QuestionOption(BaseModel):
    label: str
    value: str


class Test2Question(BaseModel):
    id: str
    prompt: str
    question_index: int
    options: list[Test2QuestionOption] = Field(default_factory=list)


class CandidateTest2Response(BaseModel):
    journey_step: str
    questions: list[Test2Question]
    current_question_index: int | None = None
    attempts: dict[str, Any] = Field(default_factory=dict)
    is_started: bool
    is_completed: bool
    score: float | None = None
    correct_answers: int | None = None
    total_questions: int
    passed: bool | None = None
    rating: str | None = None
    required_next_action: str | None = None
    result_message: str | None = None


class CandidateTest2AnswerRequest(BaseModel):
    question_index: int = Field(..., ge=0)
    answer_index: int = Field(..., ge=0)


class CandidateChatHandoffResponse(BaseModel):
    ok: bool = True
    surface: str = "max_chat"
    handoff_sent: bool


class CandidateBookingCityInfo(BaseModel):
    city_id: int
    city_name: str
    tz: str
    has_available_recruiters: bool
    available_recruiters: int
    available_slots: int


class CandidateBookingRecruiterInfo(BaseModel):
    recruiter_id: int
    recruiter_name: str
    tz: str
    available_slots: int
    next_slot_utc: datetime | None = None
    city_id: int


class CandidateBookingContextInfo(BaseModel):
    city_id: int | None = None
    city_name: str | None = None
    recruiter_id: int | None = None
    recruiter_name: str | None = None
    recruiter_tz: str | None = None
    source: str
    is_explicit: bool


class CandidateBookingContextRequest(BaseModel):
    city_id: int = Field(..., gt=0)
    recruiter_id: int | None = Field(None, gt=0)


def _candidate_info(candidate, *, city_id: int | None, city_name: str | None, user_id: int) -> CandidateInfo:
    status_value = getattr(candidate, "candidate_status", None)
    if hasattr(status_value, "value"):
        status_value = status_value.value
    return CandidateInfo(
        user_id=user_id,
        full_name=candidate.fio,
        username=candidate.username,
        candidate_id=candidate.id,
        city_id=city_id,
        city_name=city_name,
        status=status_value,
    )


def _booking_info(slot, candidate_id: int) -> BookingInfo:
    duration_minutes = slot_duration_minutes(slot)
    start_utc = slot.start_utc
    end_utc = start_utc + timedelta(minutes=duration_minutes)
    recruiter_name = getattr(getattr(slot, "recruiter", None), "name", None) or ""
    return BookingInfo(
        booking_id=slot.id,
        slot_id=slot.id,
        candidate_id=candidate_id,
        recruiter_name=recruiter_name,
        start_utc=start_utc,
        end_utc=end_utc,
        status=slot.status,
        meet_link=None,
        address=None,
    )


def _booking_city_info(city: CandidateBookingCity) -> CandidateBookingCityInfo:
    return CandidateBookingCityInfo(
        city_id=city.city_id,
        city_name=city.city_name,
        tz=city.timezone_name,
        has_available_recruiters=city.has_available_recruiters,
        available_recruiters=city.available_recruiters,
        available_slots=city.available_slots,
    )


def _booking_recruiter_info(recruiter: CandidateBookingRecruiter) -> CandidateBookingRecruiterInfo:
    return CandidateBookingRecruiterInfo(
        recruiter_id=recruiter.recruiter_id,
        recruiter_name=recruiter.recruiter_name,
        tz=recruiter.timezone_name,
        available_slots=recruiter.available_slots,
        next_slot_utc=recruiter.next_slot_utc,
        city_id=recruiter.city_id,
    )


def _booking_context_info(envelope: CandidateBookingContextEnvelope) -> CandidateBookingContextInfo:
    return CandidateBookingContextInfo(
        city_id=envelope.city_id,
        city_name=envelope.city_name,
        recruiter_id=envelope.recruiter_id,
        recruiter_name=envelope.recruiter_name,
        recruiter_tz=envelope.recruiter_tz,
        source=envelope.source,
        is_explicit=envelope.is_explicit,
    )


def _test1_question(question: dict[str, Any]) -> Test1Question:
    return Test1Question(
        id=str(question["id"]),
        prompt=str(question["prompt"]),
        placeholder=question.get("placeholder"),
        helper=question.get("helper"),
        question_index=int(question["question_index"]),
        options=[
            Test1QuestionOption(
                label=str(option["label"]),
                value=str(option["value"]),
                city_id=option.get("city_id"),
                tz=option.get("tz"),
            )
            for option in list(question.get("options") or [])
        ],
    )


def _candidate_test1_response(envelope: CandidateTest1Envelope) -> CandidateTest1Response:
    decision = envelope.screening_decision
    return CandidateTest1Response(
        journey_step=envelope.journey_session.current_step_key,
        questions=[_test1_question(question) for question in envelope.questions],
        draft_answers=envelope.draft_answers,
        is_completed=envelope.is_completed,
        screening_decision=(
            CandidateTest1Decision(
                outcome=str(decision["outcome"]),
                reason_code=str(decision["reason_code"]),
                explanation=str(decision["explanation"]),
                strictness=str(decision["strictness"]),
                required_next_action=str(decision["required_next_action"]),
            )
            if isinstance(decision, dict)
            else None
        ),
        interview_offer=(
            dict(envelope.interview_offer)
            if isinstance(envelope.interview_offer, dict)
            else envelope.interview_offer
        ),
        required_next_action=envelope.required_next_action,
    )


def _candidate_test2_response(envelope: CandidateTest2Envelope) -> CandidateTest2Response:
    return CandidateTest2Response(
        journey_step=envelope.journey_session.current_step_key,
        questions=[
            Test2Question(
                id=str(question["id"]),
                prompt=str(question["prompt"]),
                question_index=int(question["question_index"]),
                options=[
                    Test2QuestionOption(
                        label=str(option["label"]),
                        value=str(option["value"]),
                    )
                    for option in list(question.get("options") or [])
                ],
            )
            for question in envelope.questions
        ],
        current_question_index=envelope.current_question_index,
        attempts=envelope.attempts,
        is_started=envelope.is_started,
        is_completed=envelope.is_completed,
        score=envelope.score,
        correct_answers=envelope.correct_answers,
        total_questions=envelope.total_questions,
        passed=envelope.passed,
        rating=envelope.rating,
        required_next_action=envelope.required_next_action,
        result_message=envelope.result_message,
    )


def _candidate_intro_day_response(envelope: CandidateIntroDayEnvelope) -> CandidateIntroDayResponse:
    if envelope.slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intro day slot not found")
    duration_minutes = slot_duration_minutes(envelope.slot)
    start_utc = envelope.slot.start_utc
    end_utc = start_utc + timedelta(minutes=duration_minutes)
    return CandidateIntroDayResponse(
        booking_id=int(envelope.slot.id),
        city_name=envelope.city_name,
        recruiter_name=envelope.recruiter_name,
        start_utc=start_utc,
        end_utc=end_utc,
        address=envelope.intro_address,
        intro_contact=envelope.intro_contact,
        contact_name=envelope.contact_name,
        contact_phone=envelope.contact_phone,
        status=str(envelope.confirm_state or envelope.slot.status),
    )


def _status_state_label(state: str) -> str:
    mapping = {
        "done": "Готово",
        "current": "Сейчас",
        "pending": "Дальше",
        "review": "Проверка",
    }
    return mapping.get(state, "Дальше")


def _status_card(
    *,
    test1: CandidateTest1Response,
    journey: CandidateJourneyResponse | None = None,
    manual_slot_requested: bool = False,
    candidate_status: str | None = None,
    intro_day_available: bool = False,
) -> CandidateJourneyStatusCard:
    active_booking = journey.active_booking if journey is not None else None
    status_slug = str(candidate_status or "").strip().lower()
    decision = test1.screening_decision
    if intro_day_available:
        return CandidateJourneyStatusCard(
            title="Ознакомительный день назначен",
            body="Проверьте детали встречи и подтвердите участие. Если что-то нужно уточнить, откройте чат MAX.",
            tone="success",
        )
    if status_slug in {"test2_sent"}:
        return CandidateJourneyStatusCard(
            title="Открыт Тест 2",
            body="Пройдите Тест 2 в mini app. Если нужно продолжить в чате, это можно сделать без потери прогресса.",
            tone="progress",
        )
    if status_slug in {"test2_completed"}:
        return CandidateJourneyStatusCard(
            title="Тест 2 завершён",
            body="Ожидайте приглашение на ознакомительный день. Как только он будет назначен, покажем детали здесь и в чате MAX.",
            tone="success",
        )
    if active_booking is not None:
        return CandidateJourneyStatusCard(
            title="Собеседование уже назначено",
            body="Проверьте время встречи, памятку и при необходимости подтвердите запись.",
            tone="success",
        )
    if manual_slot_requested:
        return CandidateJourneyStatusCard(
            title="Пожелания по времени отправлены",
            body="Свободного слота не было, поэтому мы передали рекрутеру ваше удобное время. Дальше покажем обновление здесь или в чате MAX.",
            tone="progress",
        )
    if not test1.is_completed:
        return CandidateJourneyStatusCard(
            title="Нужно закончить анкету",
            body="Ответьте на вопросы Test1. После этого мы сразу покажем следующий шаг.",
            tone="progress",
        )
    if decision is None:
        return CandidateJourneyStatusCard(
            title="Ответы приняты",
            body="Мы готовим следующий шаг и скоро покажем, что делать дальше.",
            tone="progress",
        )
    action = str(decision.required_next_action or "").strip()
    if action == "select_interview_slot":
        return CandidateJourneyStatusCard(
            title="Можно записаться на собеседование",
            body=decision.explanation,
            tone="success",
        )
    if action == "manual_review":
        return CandidateJourneyStatusCard(
            title="Нужна ручная проверка",
            body=decision.explanation,
            tone="warn",
        )
    return CandidateJourneyStatusCard(
        title="Шаг обновлён",
        body=decision.explanation,
        tone="progress",
    )


def _primary_action(
    *,
    test1: CandidateTest1Response,
    active_booking: BookingInfo | None,
    manual_slot_requested: bool = False,
    candidate_status: str | None = None,
    intro_day_available: bool = False,
) -> CandidateJourneyPrimaryAction:
    status_slug = str(candidate_status or "").strip().lower()
    if intro_day_available:
        return CandidateJourneyPrimaryAction(
            key="review_intro_day",
            label="Проверить детали ознакомительного дня",
            kind="intro_day",
            detail="Откройте детали, подтвердите участие и сохраните адрес встречи.",
        )
    if status_slug in {"test2_sent"}:
        return CandidateJourneyPrimaryAction(
            key="continue_test2",
            label="Пройти Тест 2",
            kind="test2",
            detail="Откройте вопросы в mini app. При необходимости можно продолжить в чате MAX.",
        )
    if not test1.is_completed:
        return CandidateJourneyPrimaryAction(
            key="continue_test1",
            label="Продолжить анкету",
            kind="test1",
            detail="Нужно ответить на оставшиеся вопросы.",
        )
    if manual_slot_requested:
        return CandidateJourneyPrimaryAction(
            key="chat_fallback",
            label="Открыть чат MAX",
            kind="chat",
            detail="Пожелания по времени уже отправлены. Если хотите уточнить детали, продолжим в чате MAX.",
        )
    if active_booking is not None:
        booking_status = str(active_booking.status or "").lower()
        if booking_status in {"confirmed", "confirmed_by_candidate"}:
            return CandidateJourneyPrimaryAction(
                key="review_booking",
                label="Проверить детали встречи",
                kind="booking",
                detail="Посмотрите время собеседования и памятку.",
            )
        return CandidateJourneyPrimaryAction(
            key="confirm_booking",
            label="Подтвердить встречу",
            kind="booking",
            detail="Подтвердите запись, чтобы мы закрепили слот.",
        )
    if str(test1.required_next_action or "").strip() == "select_interview_slot":
        return CandidateJourneyPrimaryAction(
            key="select_slot",
            label="Выбрать время",
            kind="booking",
            detail="Откройте доступные слоты и выберите удобный вариант.",
        )
    return CandidateJourneyPrimaryAction(
        key="chat_fallback",
        label="Открыть чат MAX",
        kind="chat",
        detail="Если что-то пошло не так, продолжим в чате.",
    )


def _timeline(
    *,
    test1: CandidateTest1Response,
    active_booking: BookingInfo | None,
    manual_slot_requested: bool = False,
    candidate_status: str | None = None,
    intro_day_available: bool = False,
) -> list[CandidateJourneyTimelineStep]:
    status_slug = str(candidate_status or "").strip().lower()
    screening_done = test1.is_completed
    can_book = str(test1.required_next_action or "").strip() == "select_interview_slot"
    booking_done = active_booking is not None
    booking_confirmed = booking_done and str(active_booking.status or "").lower() in {"confirmed", "confirmed_by_candidate"}
    steps = [
        CandidateJourneyTimelineStep(
            key="launch",
            label="Вход в mini app",
            state="done",
            state_label=_status_state_label("done"),
            detail="MAX mini app открыт и кандидатский доступ подтверждён.",
        ),
        CandidateJourneyTimelineStep(
            key="test1",
            label="Анкета Test1",
            state="done" if screening_done else "current",
            state_label=_status_state_label("done" if screening_done else "current"),
            detail="Ответьте на вопросы, чтобы перейти к следующему шагу." if not screening_done else "Анкета завершена.",
        ),
        CandidateJourneyTimelineStep(
            key="screening",
            label="Решение по скринингу",
            state="done" if screening_done else "pending",
            state_label=_status_state_label("done" if screening_done else "pending"),
            detail=test1.screening_decision.explanation if test1.screening_decision else "Покажем результат сразу после анкеты.",
        ),
        CandidateJourneyTimelineStep(
            key="booking",
            label="Выбор времени",
            state=(
                "done"
                if booking_done
                else ("current" if manual_slot_requested or can_book else "pending")
            ),
            state_label=_status_state_label(
                "done"
                if booking_done
                else ("current" if manual_slot_requested or can_book else "pending")
            ),
            detail=(
                "Слот уже выбран."
                if booking_done
                else (
                    "Свободных слотов не было, поэтому мы передали рекрутеру удобное время."
                    if manual_slot_requested
                    else "Доступные интервалы появятся после допуска к собеседованию."
                )
            ),
        ),
        CandidateJourneyTimelineStep(
            key="confirm",
            label="Подтверждение и памятка",
            state="done" if booking_confirmed else ("current" if booking_done else "pending"),
            state_label=_status_state_label("done" if booking_confirmed else ("current" if booking_done else "pending")),
            detail="Памятка к встрече уже доступна." if booking_done else "После записи покажем время встречи и что взять с собой.",
        ),
        CandidateJourneyTimelineStep(
            key="test2",
            label="Тест 2",
            state=(
                "done"
                if status_slug in {"test2_completed", "intro_day_scheduled", "intro_day_confirmed_preliminary", "intro_day_confirmed_day_of"}
                else ("current" if status_slug == "test2_sent" else "pending")
            ),
            state_label=_status_state_label(
                "done"
                if status_slug in {"test2_completed", "intro_day_scheduled", "intro_day_confirmed_preliminary", "intro_day_confirmed_day_of"}
                else ("current" if status_slug == "test2_sent" else "pending")
            ),
            detail=(
                "Тест 2 уже завершён."
                if status_slug in {"test2_completed", "intro_day_scheduled", "intro_day_confirmed_preliminary", "intro_day_confirmed_day_of"}
                else (
                    "Тест 2 уже открыт. Пройдите его здесь в mini app."
                    if status_slug == "test2_sent"
                    else "После интервью откроем Тест 2."
                )
            ),
        ),
        CandidateJourneyTimelineStep(
            key="intro_day",
            label="Ознакомительный день",
            state="current" if intro_day_available else "pending",
            state_label=_status_state_label("current" if intro_day_available else "pending"),
            detail=(
                "Детали встречи уже доступны, подтвердите участие."
                if intro_day_available
                else "После успешного Теста 2 здесь появится приглашение и детали встречи."
            ),
        ),
    ]
    return steps


def _content_card(title: str, body: str, *, tone: str = "neutral") -> CandidateJourneyContentCard:
    return CandidateJourneyContentCard(title=title, body=body, tone=tone)


def _contact_phone(request: CandidateContactBindRequest) -> str | None:
    if request.phone and request.phone.strip():
        return request.phone.strip()
    contact = request.contact or {}
    for key in ("phone_number", "phone", "msisdn"):
        value = contact.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _candidate_contact_bind_response(
    envelope: CandidateContactBindEnvelope,
) -> CandidateContactBindResponse:
    return CandidateContactBindResponse(
        status=envelope.status,
        message=envelope.message,
        start_param=envelope.start_param,
        application_id=envelope.application_id,
        expires_at=envelope.expires_at,
    )


def _candidate_manual_availability_response(
    envelope: CandidateManualAvailabilityEnvelope,
) -> CandidateManualAvailabilityResponse:
    return CandidateManualAvailabilityResponse(
        status=envelope.status,
        message=envelope.message,
        recruiters_notified=envelope.recruiters_notified,
    )


@router.get("/me", response_model=CandidateInfo)
async def get_candidate_access_me(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateInfo:
    profile = await load_candidate_profile(session, principal)
    return _candidate_info(
        profile.candidate,
        city_id=profile.city_id,
        city_name=profile.city_name,
        user_id=int(principal.provider_user_id),
    )


@router.post("/contact", response_model=CandidateContactBindResponse)
async def bind_candidate_access_contact(
    request: CandidateContactBindRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    x_max_init_data: Annotated[str, Header(alias="X-Max-Init-Data")],
) -> CandidateContactBindResponse:
    validated_init_data = _validated_max_init_data(init_data=x_max_init_data, settings=settings)
    phone = _contact_phone(request)
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required to restore candidate access.",
        )
    async with session.begin():
        envelope = await bind_max_candidate_by_phone(
            session,
            provider_user_id=str(validated_init_data.user.user_id),
            phone=phone,
        )
    return _candidate_contact_bind_response(envelope)


@router.get("/journey", response_model=CandidateJourneyResponse)
async def get_candidate_access_journey(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateJourneyResponse:
    envelope = await load_candidate_journey(session, principal)
    test1 = _candidate_test1_response(await load_candidate_test1_state(session, principal))
    candidate_status = getattr(envelope.profile.candidate, "candidate_status", None)
    if hasattr(candidate_status, "value"):
        candidate_status = candidate_status.value
    try:
        intro_day = await load_candidate_intro_day(session, principal)
    except HTTPException:
        intro_day = None
    manual_slot_requested = (
        envelope.active_booking is None
        and getattr(envelope.profile.candidate, "manual_slot_response_at", None) is not None
    )
    response = CandidateJourneyResponse(
        candidate=_candidate_info(
            envelope.profile.candidate,
            city_id=envelope.profile.city_id,
            city_name=envelope.profile.city_name,
            user_id=int(principal.provider_user_id),
        ),
        session=JourneySessionInfo(
            journey_key=envelope.journey_session.journey_key,
            journey_version=envelope.journey_session.journey_version,
            current_step_key=envelope.journey_session.current_step_key,
            status=envelope.journey_session.status,
            application_id=envelope.journey_session.application_id,
            last_surface=envelope.journey_session.last_surface,
            last_auth_method=envelope.journey_session.last_auth_method,
            session_version=envelope.journey_session.session_version,
        ),
        active_booking=(
            _booking_info(envelope.active_booking, envelope.profile.candidate.id)
            if envelope.active_booking is not None
            else None
        ),
        screening_decision=test1.screening_decision,
    )
    response.timeline = _timeline(
        test1=test1,
        active_booking=response.active_booking,
        manual_slot_requested=manual_slot_requested,
        candidate_status=candidate_status,
        intro_day_available=intro_day is not None,
    )
    response.primary_action = _primary_action(
        test1=test1,
        active_booking=response.active_booking,
        manual_slot_requested=manual_slot_requested,
        candidate_status=candidate_status,
        intro_day_available=intro_day is not None,
    )
    response.status_card = _status_card(
        test1=test1,
        journey=response,
        manual_slot_requested=manual_slot_requested,
        candidate_status=candidate_status,
        intro_day_available=intro_day is not None,
    )
    response.prep_card = _content_card(
        "Что дальше",
        (
            "После записи проверьте время собеседования, зарядите телефон и подготовьте тихое место для разговора."
            if intro_day is None and response.active_booking is not None
            else (
                "Сохраните адрес, контакт и время ознакомительного дня. Подтверждение можно сделать здесь или в чате MAX."
                if intro_day is not None
                else (
                    "Пройдите Тест 2 в mini app. После результата сразу покажем следующий шаг."
                    if str(candidate_status or "").strip().lower() == "test2_sent"
                    else (
                        "Мы уже получили пожелания по времени. Как только подберём слот, обновим статус здесь и в чате MAX."
                        if manual_slot_requested
                        else "После анкеты мы сразу покажем следующий шаг и доступное время для собеседования."
                    )
                )
            )
        ),
        tone="accent",
    )
    response.company_card = _content_card(
        "О компании",
        "RecruitSmart помогает быстро пройти путь от первого контакта до интервью в одном понятном канале.",
    )
    response.help_card = _content_card(
        "Нужна помощь",
        (
            "Если хотите уточнить город, время или детали анкеты, откройте чат MAX и продолжите с рекрутером."
            if manual_slot_requested
            else "Если что-то не загрузилось или нужен другой слот, откройте чат MAX и продолжите с рекрутером."
        ),
    )
    return response


@router.get("/cities", response_model=list[CandidateBookingCityInfo])
async def get_candidate_access_cities(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[CandidateBookingCityInfo]:
    cities = await list_candidate_booking_cities(session, principal)
    return [_booking_city_info(city) for city in cities]


@router.get("/recruiters", response_model=list[CandidateBookingRecruiterInfo])
async def get_candidate_access_recruiters(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    city_id: Annotated[int, Query(gt=0, description="City ID to load recruiters for")] = ...,
) -> list[CandidateBookingRecruiterInfo]:
    recruiters = await list_candidate_booking_recruiters(session, principal, city_id=city_id)
    return [_booking_recruiter_info(recruiter) for recruiter in recruiters]


@router.get("/booking-context", response_model=CandidateBookingContextInfo)
async def get_candidate_access_booking_context(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateBookingContextInfo:
    envelope = await load_candidate_booking_context(session, principal)
    return _booking_context_info(envelope)


@router.post("/booking-context", response_model=CandidateBookingContextInfo)
async def save_candidate_access_booking_context(
    request: CandidateBookingContextRequest,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateBookingContextInfo:
    async with session.begin():
        envelope = await save_candidate_booking_context(
            session,
            principal,
            city_id=request.city_id,
            recruiter_id=request.recruiter_id,
        )
    return _booking_context_info(envelope)


@router.post("/manual-availability", response_model=CandidateManualAvailabilityResponse)
async def save_candidate_access_manual_availability(
    request: CandidateManualAvailabilityRequest,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateManualAvailabilityResponse:
    async with session.begin():
        envelope = await save_candidate_manual_availability(
            session,
            principal,
            note=request.note,
            window_start=request.window_start,
            window_end=request.window_end,
            timezone_label=request.timezone_label,
        )
    return _candidate_manual_availability_response(envelope)


@router.get("/test1", response_model=CandidateTest1Response)
async def get_candidate_access_test1(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateTest1Response:
    envelope = await load_candidate_test1_state(session, principal)
    return _candidate_test1_response(envelope)


@router.post("/test1/answers", response_model=CandidateTest1Response)
async def save_candidate_access_test1_answers(
    request: CandidateTest1AnswersRequest,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateTest1Response:
    async with session.begin():
        envelope = await save_candidate_test1_answers(
            session,
            principal,
            answers=request.answers,
        )
    return _candidate_test1_response(envelope)


@router.post("/test1/complete", response_model=CandidateTest1Response)
async def complete_candidate_access_test1(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateTest1Response:
    async with session.begin():
        envelope = await complete_candidate_test1(session, principal)
    return _candidate_test1_response(envelope)


@router.get("/test2", response_model=CandidateTest2Response)
async def get_candidate_access_test2(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateTest2Response:
    async with session.begin():
        envelope = await load_candidate_test2_state(session, principal)
    return _candidate_test2_response(envelope)


@router.post("/test2/answers", response_model=CandidateTest2Response)
async def submit_candidate_access_test2_answer(
    request: CandidateTest2AnswerRequest,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateTest2Response:
    async with session.begin():
        envelope = await submit_candidate_test2_answer(
            session,
            principal,
            question_index=request.question_index,
            answer_index=request.answer_index,
        )
    return _candidate_test2_response(envelope)


@router.get("/intro-day", response_model=CandidateIntroDayResponse)
async def get_candidate_access_intro_day(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateIntroDayResponse:
    envelope = await load_candidate_intro_day(session, principal)
    return _candidate_intro_day_response(envelope)


@router.post("/intro-day/confirm", response_model=CandidateIntroDayResponse)
async def confirm_candidate_access_intro_day(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CandidateIntroDayResponse:
    async with session.begin():
        envelope = await confirm_candidate_intro_day(session, principal)
    return _candidate_intro_day_response(envelope)


@router.post("/chat-handoff", response_model=CandidateChatHandoffResponse)
async def handoff_candidate_access_to_chat(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateChatHandoffResponse:
    async with session.begin():
        prompt = await activate_max_chat_handoff(session, principal)
        profile = await load_candidate_profile(session, principal)
        max_user_id = str(getattr(profile.candidate, "max_user_id", "") or "").strip()

    sent = False
    if max_user_id:
        sent = await send_max_chat_prompt(
            settings=settings,
            max_user_id=max_user_id,
            prompt=prompt,
            client_request_id=f"max:chat_handoff:{principal.access_session_id}",
            payload={"access_session_id": principal.access_session_id},
        )
    return CandidateChatHandoffResponse(handoff_sent=sent)


@router.get("/slots", response_model=list[SlotInfo])
async def get_candidate_access_slots(
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    city_id: Annotated[int | None, Query(description="Filter by city ID")] = None,
    recruiter_id: Annotated[int | None, Query(description="Filter by recruiter ID")] = None,
    from_date: Annotated[datetime | None, Query(description="Start date (UTC)")] = None,
    to_date: Annotated[datetime | None, Query(description="End date (UTC)")] = None,
) -> list[SlotInfo]:
    await ensure_candidate_booking_allowed(session, principal)
    if city_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Choose a city before loading interview slots.",
        )
    slots = await list_available_interview_slots(
        session,
        city_id=city_id,
        recruiter_id=recruiter_id,
        from_date=from_date,
        to_date=to_date,
    )
    return [
        SlotInfo(
            slot_id=slot.id,
            recruiter_id=slot.recruiter_id,
            recruiter_name=getattr(getattr(slot, "recruiter", None), "name", None) or "",
            recruiter_tz=getattr(getattr(slot, "recruiter", None), "tz", None),
            start_utc=slot.start_utc,
            end_utc=slot.start_utc + timedelta(minutes=slot_duration_minutes(slot)),
            duration_minutes=slot_duration_minutes(slot),
            is_available=True,
            city_id=slot.city_id,
            city_name=getattr(getattr(slot, "city", None), "name_plain", None),
        )
        for slot in slots
    ]


@router.post("/bookings", response_model=BookingInfo, status_code=status.HTTP_201_CREATED)
async def create_candidate_access_booking(
    request: CreateBookingRequest,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> BookingInfo:
    async with session.begin():
        candidate, slot = await create_candidate_booking(session, principal, slot_id=request.slot_id)
    return _booking_info(slot, candidate.id)


@router.post("/bookings/{booking_id}/confirm", response_model=BookingInfo)
async def confirm_candidate_access_booking(
    booking_id: int,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> BookingInfo:
    async with session.begin():
        slot = await confirm_candidate_booking(session, principal, booking_id=booking_id)
    return _booking_info(slot, principal.candidate_id)


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingInfo)
async def reschedule_candidate_access_booking(
    booking_id: int,
    request: RescheduleBookingRequest,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> BookingInfo:
    async with session.begin():
        candidate, slot = await reschedule_candidate_booking(
            session,
            principal,
            booking_id=booking_id,
            new_slot_id=request.new_slot_id,
        )
    return _booking_info(slot, candidate.id)


@router.post("/bookings/{booking_id}/cancel", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def cancel_candidate_access_booking(
    booking_id: int,
    request: CancelBookingRequest,
    principal: Annotated[CandidateAccessPrincipal, Depends(get_max_candidate_access_principal)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Response:
    del request
    async with session.begin():
        await cancel_candidate_booking(session, principal, booking_id=booking_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


CandidateJourneyResponse.model_rebuild()

__all__ = ["router"]
