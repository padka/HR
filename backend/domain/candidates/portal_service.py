"""Channel-agnostic candidate portal helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.apps.bot.config import DEFAULT_TZ, TEST1_QUESTIONS, refresh_questions_bank
from backend.apps.bot.test1_validation import apply_partial_validation, convert_age
from backend.core.settings import get_settings
from backend.domain import analytics
from backend.domain.candidate_status_service import CandidateStatusService
from backend.domain.candidates.models import (
    CandidateJourneySession,
    CandidateJourneySessionStatus,
    CandidateJourneyStepState,
    CandidateJourneyStepStatus,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    QuestionAnswer,
    TestResult,
    User,
)
from backend.domain.candidates.status import CandidateStatus, STATUS_LABELS
from backend.domain.models import City, Slot, SlotStatus
from backend.domain.repositories import find_city_by_plain_name
from backend.domain.slot_service import confirm_slot_by_candidate, reject_slot, reserve_slot

PORTAL_JOURNEY_KEY = "candidate_portal"
PORTAL_JOURNEY_VERSION = "v1"
PORTAL_SESSION_KEY = "candidate_portal"
PORTAL_TOKEN_SALT = "candidate-portal-link"
PORTAL_DEFAULT_ENTRY_CHANNEL = "web"
PORTAL_STEP_LABELS = {
    "profile": "Профиль",
    "screening": "Анкета",
    "slot_selection": "Собеседование",
    "status": "Статус",
}
PORTAL_ACTIVE_SLOT_STATUSES = {
    SlotStatus.PENDING,
    SlotStatus.BOOKED,
    SlotStatus.CONFIRMED,
    SlotStatus.CONFIRMED_BY_CANDIDATE,
}

_status_service = CandidateStatusService()


class CandidatePortalError(ValueError):
    """Base class for candidate portal validation errors."""


class CandidatePortalAuthError(CandidatePortalError):
    """Raised when a portal access token or session is invalid."""


@dataclass(frozen=True)
class CandidatePortalAccess:
    candidate_uuid: str | None
    telegram_id: int | None
    entry_channel: str
    source_channel: str


def _serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt=PORTAL_TOKEN_SALT)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sign_candidate_portal_token(
    *,
    candidate_uuid: str | None = None,
    telegram_id: int | None = None,
    entry_channel: str = PORTAL_DEFAULT_ENTRY_CHANNEL,
    source_channel: str = "portal",
) -> str:
    if not candidate_uuid and not telegram_id:
        raise CandidatePortalError("Candidate portal token requires candidate_uuid or telegram_id")
    return _serializer().dumps(
        {
            "candidate_uuid": candidate_uuid,
            "telegram_id": telegram_id,
            "entry_channel": entry_channel or PORTAL_DEFAULT_ENTRY_CHANNEL,
            "source_channel": source_channel or "portal",
        }
    )


def parse_candidate_portal_token(value: str) -> CandidatePortalAccess:
    settings = get_settings()
    try:
        payload = _serializer().loads(
            value,
            max_age=settings.candidate_portal_token_ttl_seconds,
        )
    except SignatureExpired as exc:
        raise CandidatePortalAuthError("Ссылка для входа устарела.") from exc
    except BadSignature as exc:
        raise CandidatePortalAuthError("Ссылка для входа недействительна.") from exc

    candidate_uuid = str(payload.get("candidate_uuid") or "").strip() or None
    telegram_id_raw = payload.get("telegram_id")
    telegram_id = int(telegram_id_raw) if telegram_id_raw not in (None, "") else None
    if not candidate_uuid and not telegram_id:
        raise CandidatePortalAuthError("Ссылка не содержит идентификатор кандидата.")

    return CandidatePortalAccess(
        candidate_uuid=candidate_uuid,
        telegram_id=telegram_id,
        entry_channel=str(payload.get("entry_channel") or PORTAL_DEFAULT_ENTRY_CHANNEL),
        source_channel=str(payload.get("source_channel") or "portal"),
    )


def build_candidate_portal_url(
    *,
    candidate_uuid: str | None = None,
    telegram_id: int | None = None,
    entry_channel: str = PORTAL_DEFAULT_ENTRY_CHANNEL,
    source_channel: str = "portal",
) -> str:
    settings = get_settings()
    token = sign_candidate_portal_token(
        candidate_uuid=candidate_uuid,
        telegram_id=telegram_id,
        entry_channel=entry_channel,
        source_channel=source_channel,
    )
    base = (settings.candidate_portal_public_url or settings.crm_public_url or settings.bot_backend_url or "").rstrip("/")
    if not base:
        return f"/candidate/start/{token}"
    if base.endswith("/candidate"):
        return f"{base}/start/{token}"
    return f"{base}/candidate/start/{token}"


def is_candidate_portal_session_valid(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    candidate_id = payload.get("candidate_id")
    last_seen_at = payload.get("last_seen_at")
    if not isinstance(candidate_id, int) or candidate_id <= 0:
        return False
    if not isinstance(last_seen_at, (int, float)):
        return False
    settings = get_settings()
    age_seconds = _utcnow().timestamp() - float(last_seen_at)
    return age_seconds <= float(settings.candidate_portal_session_ttl_seconds)


def touch_candidate_portal_session(payload: dict[str, Any]) -> dict[str, Any]:
    next_payload = dict(payload)
    next_payload["last_seen_at"] = _utcnow().timestamp()
    return next_payload


async def resolve_candidate_portal_user(
    session: AsyncSession,
    access: CandidatePortalAccess,
) -> User:
    user: User | None = None

    if access.candidate_uuid:
        user = await session.scalar(
            select(User).where(User.candidate_id == access.candidate_uuid)
        )

    if user is None and access.telegram_id is not None:
        user = await session.scalar(
            select(User).where(
                or_(
                    User.telegram_id == access.telegram_id,
                    User.telegram_user_id == access.telegram_id,
                )
            )
        )

    now = _utcnow()
    if user is None:
        if access.telegram_id is None:
            raise CandidatePortalAuthError("Кандидат по ссылке не найден.")
        user = User(
            telegram_id=access.telegram_id,
            telegram_user_id=access.telegram_id,
            telegram_linked_at=now,
            fio=f"TG {access.telegram_id}",
            source=access.source_channel or "portal",
            messenger_platform="telegram",
            last_activity=now,
        )
        session.add(user)
        await session.flush()
    else:
        if access.telegram_id is not None:
            if user.telegram_id is None:
                user.telegram_id = access.telegram_id
            if user.telegram_user_id is None:
                user.telegram_user_id = access.telegram_id
            if user.telegram_linked_at is None:
                user.telegram_linked_at = now
            if not user.messenger_platform:
                user.messenger_platform = "telegram"

    user.last_activity = now
    if access.source_channel and not user.source:
        user.source = access.source_channel
    await session.flush()
    return user


async def get_candidate_portal_user(
    session: AsyncSession,
    candidate_id: int,
) -> User | None:
    return await session.scalar(
        select(User).where(User.id == candidate_id)
    )


async def ensure_candidate_portal_session(
    session: AsyncSession,
    candidate: User,
    *,
    entry_channel: str = PORTAL_DEFAULT_ENTRY_CHANNEL,
) -> CandidateJourneySession:
    journey = await session.scalar(
        select(CandidateJourneySession)
        .where(
            CandidateJourneySession.candidate_id == candidate.id,
            CandidateJourneySession.journey_key == PORTAL_JOURNEY_KEY,
            CandidateJourneySession.status == CandidateJourneySessionStatus.ACTIVE.value,
        )
        .options(selectinload(CandidateJourneySession.step_states))
        .order_by(CandidateJourneySession.id.desc())
        .limit(1)
    )
    now = _utcnow()
    if journey is None:
        journey = CandidateJourneySession(
            candidate_id=candidate.id,
            journey_key=PORTAL_JOURNEY_KEY,
            journey_version=PORTAL_JOURNEY_VERSION,
            entry_channel=entry_channel or PORTAL_DEFAULT_ENTRY_CHANNEL,
            current_step_key="profile",
            status=CandidateJourneySessionStatus.ACTIVE.value,
            started_at=now,
            last_activity_at=now,
        )
        session.add(journey)
        await session.flush()
        return journey

    journey.entry_channel = journey.entry_channel or entry_channel or PORTAL_DEFAULT_ENTRY_CHANNEL
    journey.last_activity_at = now
    await session.flush()
    return journey


async def upsert_step_state(
    session: AsyncSession,
    journey: CandidateJourneySession,
    *,
    step_key: str,
    step_type: str = "form",
    status: str,
    payload: Optional[dict[str, Any]] = None,
) -> CandidateJourneyStepState:
    step_state = next((item for item in journey.step_states if item.step_key == step_key), None)
    now = _utcnow()
    if step_state is None:
        step_state = CandidateJourneyStepState(
            session_id=journey.id,
            step_key=step_key,
            step_type=step_type,
            status=status,
            payload_json=payload,
            started_at=now,
            updated_at=now,
            completed_at=now if status == CandidateJourneyStepStatus.COMPLETED.value else None,
        )
        journey.step_states.append(step_state)
        session.add(step_state)
    else:
        step_state.step_type = step_type
        step_state.status = status
        step_state.payload_json = payload
        step_state.updated_at = now
        if status == CandidateJourneyStepStatus.COMPLETED.value:
            step_state.completed_at = step_state.completed_at or now
        elif status in {
            CandidateJourneyStepStatus.PENDING.value,
            CandidateJourneyStepStatus.IN_PROGRESS.value,
        }:
            step_state.completed_at = None
    journey.last_activity_at = now
    await session.flush()
    return step_state


def _is_placeholder_fio(value: Optional[str]) -> bool:
    cleaned = (value or "").strip()
    return not cleaned or cleaned.startswith("TG ")


def _normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        raise CandidatePortalError("Укажите телефон в формате +7XXXXXXXXXX.")
    return f"+{digits}"


async def _resolve_city(session: AsyncSession, *, city_id: int | None = None, city_name: str | None = None) -> City | None:
    if city_id:
        return await session.get(City, city_id)
    if city_name:
        return await find_city_by_plain_name(city_name)
    return None


def _question_input_type(question: dict[str, Any]) -> str:
    if question.get("options"):
        return "single_choice"
    if question.get("id") == "age":
        return "number"
    return "text"


def get_candidate_portal_questions() -> list[dict[str, Any]]:
    refresh_questions_bank()
    questions: list[dict[str, Any]] = []
    for index, question in enumerate(TEST1_QUESTIONS, start=1):
        question_id = str(question.get("id") or "").strip()
        if question_id in {"fio", "city"}:
            continue
        questions.append(
            {
                "index": index,
                "id": question_id,
                "prompt": question.get("prompt") or question.get("text") or "",
                "placeholder": question.get("placeholder"),
                "helper": question.get("helper"),
                "options": list(question.get("options") or []),
                "input_type": _question_input_type(question),
                "required": True,
            }
        )
    return questions


async def list_candidate_portal_cities(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await session.execute(
        select(City)
        .where(City.active.is_(True))
        .order_by(func.lower(City.name))
    )
    return [
        {
            "id": city.id,
            "name": city.name_plain,
            "tz": city.tz,
        }
        for city in rows.scalars().all()
    ]


async def get_latest_test1_result(session: AsyncSession, candidate_id: int) -> TestResult | None:
    return await session.scalar(
        select(TestResult)
        .where(
            TestResult.user_id == candidate_id,
            TestResult.rating == "TEST1",
        )
        .order_by(TestResult.created_at.desc(), TestResult.id.desc())
        .limit(1)
    )


async def get_candidate_active_slot(session: AsyncSession, candidate: User) -> Slot | None:
    telegram_ids = {
        int(value)
        for value in (candidate.telegram_id, candidate.telegram_user_id)
        if value is not None
    }
    conditions = [Slot.candidate_id == candidate.candidate_id]
    if telegram_ids:
        conditions.append(Slot.candidate_tg_id.in_(telegram_ids))

    return await session.scalar(
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(
            or_(*conditions),
            func.lower(Slot.status).in_([status.lower() for status in PORTAL_ACTIVE_SLOT_STATUSES]),
            func.lower(func.coalesce(Slot.purpose, "interview")) == "interview",
        )
        .order_by(Slot.start_utc.asc(), Slot.id.asc())
        .limit(1)
    )


async def list_candidate_portal_slots(
    session: AsyncSession,
    *,
    city_id: int,
    exclude_slot_id: int | None = None,
    limit: int = 12,
) -> list[Slot]:
    now = _utcnow()
    stmt = (
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(
            Slot.city_id == city_id,
            func.lower(Slot.status) == SlotStatus.FREE,
            Slot.start_utc >= now,
            Slot.candidate_id.is_(None),
            Slot.candidate_tg_id.is_(None),
            func.lower(func.coalesce(Slot.purpose, "interview")) == "interview",
        )
        .order_by(Slot.start_utc.asc(), Slot.id.asc())
        .limit(limit)
    )
    if exclude_slot_id is not None:
        stmt = stmt.where(Slot.id != exclude_slot_id)
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


def serialize_portal_slot(slot: Slot) -> dict[str, Any]:
    duration = int(getattr(slot, "duration_min", 60) or 60)
    start_utc = slot.start_utc
    end_utc = start_utc + timedelta(minutes=duration) if start_utc else None
    return {
        "id": slot.id,
        "status": slot.status,
        "purpose": slot.purpose,
        "start_utc": start_utc.isoformat() if start_utc else None,
        "end_utc": end_utc.isoformat() if end_utc else None,
        "duration_min": duration,
        "city_id": slot.city_id,
        "city_name": slot.city.name_plain if getattr(slot, "city", None) else None,
        "recruiter_id": slot.recruiter_id,
        "recruiter_name": getattr(getattr(slot, "recruiter", None), "name", None),
        "candidate_tz": slot.candidate_tz,
        "tz_name": slot.tz_name,
    }


def serialize_chat_message(message: ChatMessage) -> dict[str, Any]:
    return {
        "id": message.id,
        "direction": message.direction,
        "channel": message.channel,
        "text": message.text,
        "status": message.status,
        "author_label": message.author_label,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _next_action_text(
    *,
    current_step: str,
    has_available_slots: bool,
    active_slot: Slot | None,
) -> str:
    if current_step == "profile":
        return "Заполните профиль, чтобы сохранить контакт и продолжить анкету."
    if current_step == "screening":
        return "Ответьте на короткую анкету. Прогресс сохранится автоматически."
    if current_step == "slot_selection":
        return "Выберите удобное время для собеседования."
    if active_slot is not None:
        status_value = (active_slot.status or "").lower()
        if status_value == SlotStatus.PENDING:
            return "Слот отправлен рекрутеру на подтверждение."
        if status_value == SlotStatus.CONFIRMED_BY_CANDIDATE:
            return "Собеседование подтверждено. Следите за напоминаниями и статусом."
        return "Проверьте детали собеседования и при необходимости подтвердите или перенесите слот."
    if has_available_slots:
        return "Выберите слот, чтобы завершить запись на собеседование."
    return "Слотов пока нет. Мы сохранили ваш прогресс и покажем следующий шаг здесь."


async def build_candidate_portal_journey(
    session: AsyncSession,
    candidate: User,
    *,
    entry_channel: str = PORTAL_DEFAULT_ENTRY_CHANNEL,
) -> dict[str, Any]:
    journey = await ensure_candidate_portal_session(
        session,
        candidate,
        entry_channel=entry_channel,
    )
    step_map = {item.step_key: item for item in journey.step_states}
    profile_state = step_map.get("profile")
    screening_state = step_map.get("screening")

    test1_result = await get_latest_test1_result(session, candidate.id)
    active_slot = await get_candidate_active_slot(session, candidate)
    current_city = await _resolve_city(
        session,
        city_name=candidate.city,
    )
    available_slots = (
        await list_candidate_portal_slots(
            session,
            city_id=current_city.id,
            exclude_slot_id=active_slot.id if active_slot else None,
        )
        if current_city is not None
        else []
    )

    profile_complete = (
        not _is_placeholder_fio(candidate.fio)
        and bool((candidate.phone or "").strip())
        and current_city is not None
    )
    screening_complete = test1_result is not None
    has_available_slots = len(available_slots) > 0

    if not profile_complete:
        current_step = "profile"
    elif not screening_complete:
        current_step = "screening"
    elif active_slot is None and has_available_slots:
        current_step = "slot_selection"
    else:
        current_step = "status"

    journey.current_step_key = current_step
    journey.last_activity_at = _utcnow()
    if current_step == "profile":
        await upsert_step_state(
            session,
            journey,
            step_key="profile",
            status=CandidateJourneyStepStatus.IN_PROGRESS.value,
            payload=profile_state.payload_json if profile_state else None,
        )
    elif profile_complete:
        await upsert_step_state(
            session,
            journey,
            step_key="profile",
            status=CandidateJourneyStepStatus.COMPLETED.value,
            payload=profile_state.payload_json if profile_state else {
                "fio": candidate.fio,
                "phone": candidate.phone,
                "city_id": current_city.id if current_city else None,
            },
        )

    if screening_complete:
        await upsert_step_state(
            session,
            journey,
            step_key="screening",
            status=CandidateJourneyStepStatus.COMPLETED.value,
            payload=screening_state.payload_json if screening_state else None,
        )
    elif current_step == "screening":
        await upsert_step_state(
            session,
            journey,
            step_key="screening",
            status=CandidateJourneyStepStatus.IN_PROGRESS.value,
            payload=screening_state.payload_json if screening_state else None,
        )

    step_statuses = {
        "profile": (
            CandidateJourneyStepStatus.COMPLETED.value
            if profile_complete
            else CandidateJourneyStepStatus.IN_PROGRESS.value
        ),
        "screening": (
            CandidateJourneyStepStatus.COMPLETED.value
            if screening_complete
            else (
                CandidateJourneyStepStatus.IN_PROGRESS.value
                if current_step == "screening" or screening_state is not None
                else CandidateJourneyStepStatus.PENDING.value
            )
        ),
        "slot_selection": (
            CandidateJourneyStepStatus.COMPLETED.value
            if active_slot is not None
            else (
                CandidateJourneyStepStatus.IN_PROGRESS.value
                if screening_complete and has_available_slots and current_step in {"slot_selection", "status"}
                else CandidateJourneyStepStatus.PENDING.value
            )
        ),
        "status": (
            CandidateJourneyStepStatus.IN_PROGRESS.value
            if screening_complete
            else CandidateJourneyStepStatus.PENDING.value
        ),
    }

    messages = list(
        await session.scalars(
            select(ChatMessage)
            .where(ChatMessage.candidate_id == candidate.id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(20)
        )
    )

    return {
        "candidate": {
            "id": candidate.id,
            "candidate_id": candidate.candidate_id,
            "fio": candidate.fio,
            "phone": candidate.phone,
            "city": candidate.city,
            "city_id": current_city.id if current_city else None,
            "status": candidate.candidate_status.value if candidate.candidate_status else None,
            "status_label": STATUS_LABELS.get(candidate.candidate_status) if candidate.candidate_status else None,
            "source": candidate.source,
            "portal_url": build_candidate_portal_url(
                candidate_uuid=candidate.candidate_id,
                entry_channel=entry_channel,
                source_channel="portal",
            ),
        },
        "journey": {
            "session_id": journey.id,
            "journey_key": journey.journey_key,
            "journey_version": journey.journey_version,
            "entry_channel": journey.entry_channel,
            "current_step": current_step,
            "next_action": _next_action_text(
                current_step=current_step,
                has_available_slots=has_available_slots,
                active_slot=active_slot,
            ),
            "steps": [
                {
                    "key": key,
                    "label": label,
                    "status": step_statuses.get(key, CandidateJourneyStepStatus.PENDING.value),
                }
                for key, label in PORTAL_STEP_LABELS.items()
            ],
            "profile": {
                "fio": candidate.fio if not _is_placeholder_fio(candidate.fio) else "",
                "phone": candidate.phone or "",
                "city_id": current_city.id if current_city else None,
                "city_name": current_city.name_plain if current_city else candidate.city,
            },
            "screening": {
                "questions": get_candidate_portal_questions(),
                "draft_answers": dict(screening_state.payload_json or {}) if screening_state and screening_state.payload_json else {},
                "completed": screening_complete,
                "completed_at": test1_result.created_at.isoformat() if test1_result and test1_result.created_at else None,
            },
            "slots": {
                "available": [serialize_portal_slot(slot) for slot in available_slots],
                "active": serialize_portal_slot(active_slot) if active_slot else None,
            },
            "messages": [serialize_chat_message(message) for message in reversed(messages)],
            "cities": await list_candidate_portal_cities(session),
        },
    }


async def save_candidate_profile(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
    *,
    fio: str,
    phone: str,
    city_id: int,
) -> None:
    normalized_fio = (fio or "").strip()
    if not normalized_fio:
        raise CandidatePortalError("Укажите ФИО.")
    try:
        apply_partial_validation({"fio": normalized_fio})
    except Exception as exc:
        raise CandidatePortalError(str(exc)) from exc

    city = await session.get(City, city_id)
    if city is None or not city.active:
        raise CandidatePortalError("Выберите город из списка.")

    candidate.fio = normalized_fio
    candidate.phone = _normalize_phone(phone)
    candidate.city = city.name_plain
    candidate.last_activity = _utcnow()
    await upsert_step_state(
        session,
        journey,
        step_key="profile",
        status=CandidateJourneyStepStatus.COMPLETED.value,
        payload={
            "fio": candidate.fio,
            "phone": candidate.phone,
            "city_id": city.id,
            "city_name": city.name_plain,
        },
    )


def _normalize_screening_answers(answers: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in answers.items():
        question_key = str(key or "").strip()
        if not question_key:
            continue
        text = str(value or "").strip()
        if text:
            normalized[question_key] = text
    return normalized


def validate_screening_answers(answers: dict[str, Any]) -> dict[str, str]:
    normalized = _normalize_screening_answers(answers)
    questions = get_candidate_portal_questions()
    required_fields = [str(item["id"]) for item in questions]
    missing = [field for field in required_fields if not normalized.get(field)]
    if missing:
        raise CandidatePortalError("Заполните все вопросы анкеты.")

    age_raw = normalized.get("age")
    if age_raw is not None:
        try:
            normalized["age"] = str(convert_age(age_raw))
            apply_partial_validation({"age": int(normalized["age"])})
        except Exception as exc:
            raise CandidatePortalError(str(exc)) from exc

    return normalized


async def save_screening_draft(
    session: AsyncSession,
    journey: CandidateJourneySession,
    *,
    answers: dict[str, Any],
) -> None:
    normalized = _normalize_screening_answers(answers)
    await upsert_step_state(
        session,
        journey,
        step_key="screening",
        status=CandidateJourneyStepStatus.IN_PROGRESS.value,
        payload=normalized,
    )


async def complete_screening(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
    *,
    answers: dict[str, Any],
) -> TestResult:
    normalized = validate_screening_answers(answers)
    now = _utcnow()

    question_data = []
    for index, question in enumerate(get_candidate_portal_questions(), start=1):
        question_key = str(question["id"])
        answer = normalized.get(question_key, "")
        question_data.append(
            {
                "question_index": index,
                "question_text": question["prompt"],
                "correct_answer": None,
                "user_answer": answer,
                "attempts_count": 1 if answer else 0,
                "time_spent": 0,
                "is_correct": True,
                "overtime": False,
            }
        )

    test_result = TestResult(
        user_id=candidate.id,
        raw_score=len(question_data),
        final_score=float(len(question_data)),
        rating="TEST1",
        source="candidate_portal",
        total_time=0,
        created_at=now,
    )
    session.add(test_result)
    await session.flush()

    for item in question_data:
        session.add(
            QuestionAnswer(
                test_result_id=test_result.id,
                question_index=int(item["question_index"]),
                question_text=str(item["question_text"]),
                correct_answer=item["correct_answer"],
                user_answer=item["user_answer"],
                attempts_count=int(item["attempts_count"]),
                time_spent=int(item["time_spent"]),
                is_correct=bool(item["is_correct"]),
                overtime=bool(item["overtime"]),
            )
        )

    candidate.last_activity = now
    await _status_service.force(
        candidate,
        CandidateStatus.TEST1_COMPLETED,
        reason="candidate portal screening completed",
    )
    await _status_service.force(
        candidate,
        CandidateStatus.WAITING_SLOT,
        reason="candidate portal waiting for slot",
    )
    await upsert_step_state(
        session,
        journey,
        step_key="screening",
        status=CandidateJourneyStepStatus.COMPLETED.value,
        payload=normalized,
    )
    await analytics.log_funnel_event(
        analytics.FunnelEvent.TEST1_COMPLETED,
        user_id=candidate.telegram_id or candidate.telegram_user_id,
        candidate_id=candidate.id,
        metadata={"result": "passed", "channel": "candidate_portal"},
        session=session,
    )
    return test_result


async def create_candidate_portal_message(
    session: AsyncSession,
    candidate: User,
    *,
    text: str,
) -> ChatMessage:
    clean_text = (text or "").strip()
    if not clean_text:
        raise CandidatePortalError("Введите сообщение для рекрутера.")
    message = ChatMessage(
        candidate_id=candidate.id,
        telegram_user_id=candidate.telegram_user_id or candidate.telegram_id,
        direction=ChatMessageDirection.INBOUND.value,
        channel="candidate_portal",
        text=clean_text,
        status=ChatMessageStatus.RECEIVED.value,
        author_label=candidate.fio if not _is_placeholder_fio(candidate.fio) else "Кандидат",
    )
    candidate.last_activity = _utcnow()
    session.add(message)
    await session.flush()
    return message


async def ensure_candidate_waiting_slot(
    session: AsyncSession,
    candidate: User,
) -> None:
    target = CandidateStatus.WAITING_SLOT
    if candidate.candidate_status != target:
        await _status_service.force(
            candidate,
            target,
            reason="candidate portal slot released",
        )


async def ensure_candidate_slot_pending(
    session: AsyncSession,
    candidate: User,
) -> None:
    target = CandidateStatus.SLOT_PENDING
    if candidate.candidate_status != target:
        await _status_service.force(
            candidate,
            target,
            reason="candidate portal slot reserved",
        )


async def ensure_candidate_slot_confirmed(
    session: AsyncSession,
    candidate: User,
) -> None:
    target = CandidateStatus.INTERVIEW_CONFIRMED
    if candidate.candidate_status != target:
        await _status_service.force(
            candidate,
            target,
            reason="candidate portal slot confirmed",
        )


def resolve_candidate_timezone(*, city: City | None, candidate: User) -> str:
    return (
        (city.tz if city and city.tz else None)
        or candidate.manual_slot_timezone
        or DEFAULT_TZ
    )


def _dialect_name(session: AsyncSession) -> str:
    bind = session.get_bind()
    return bind.dialect.name if bind is not None else ""


async def reserve_candidate_portal_slot(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
    *,
    slot_id: int,
) -> dict[str, Any]:
    city = await _resolve_city(session, city_name=candidate.city)
    if city is None:
        raise CandidatePortalError("Сначала укажите город кандидата.")

    reserved_slot: Slot | None = None
    if _dialect_name(session) == "sqlite":
        existing_active = await get_candidate_active_slot(session, candidate)
        if existing_active is not None and existing_active.id != slot_id:
            raise CandidatePortalError("У вас уже есть активная запись на собеседование.")

        slot = await session.scalar(
            select(Slot)
            .options(selectinload(Slot.recruiter), selectinload(Slot.city))
            .where(Slot.id == slot_id)
        )
        if slot is None:
            raise CandidatePortalError("Слот не найден.")
        if (slot.status or "").lower() != SlotStatus.FREE or slot.candidate_id or slot.candidate_tg_id:
            raise CandidatePortalError("Слот уже занят. Обновите список и выберите другое время.")

        slot.status = SlotStatus.PENDING
        slot.candidate_id = candidate.candidate_id
        slot.candidate_tg_id = candidate.telegram_user_id or candidate.telegram_id
        slot.candidate_fio = candidate.fio
        slot.candidate_tz = resolve_candidate_timezone(city=city, candidate=candidate)
        slot.candidate_city_id = city.id
        slot.purpose = "interview"
        reserved_slot = slot
        await session.flush()
    else:
        reservation = await reserve_slot(
            slot_id,
            candidate.telegram_user_id or candidate.telegram_id,
            candidate.fio,
            resolve_candidate_timezone(city=city, candidate=candidate),
            candidate_id=candidate.candidate_id,
            candidate_city_id=city.id,
            candidate_username=candidate.username or candidate.telegram_username,
            purpose="interview",
        )
        if reservation.status != "reserved" or reservation.slot is None:
            error_messages = {
                "slot_taken": "Слот уже занят. Обновите список и выберите другое время.",
                "duplicate_candidate": "У вас уже есть активная запись на собеседование.",
                "already_reserved": "Этот слот уже закреплен за вами.",
                "not_found": "Слот не найден.",
            }
            raise CandidatePortalError(error_messages.get(reservation.status, "Не удалось забронировать слот."))
        reserved_slot = reservation.slot

    candidate.responsible_recruiter_id = reserved_slot.recruiter_id if reserved_slot else candidate.responsible_recruiter_id
    await ensure_candidate_slot_pending(session, candidate)
    await upsert_step_state(
        session,
        journey,
        step_key="slot_selection",
        step_type="schedule",
        status=CandidateJourneyStepStatus.COMPLETED.value,
        payload={"slot_id": reserved_slot.id if reserved_slot else slot_id, "action": "reserve"},
    )
    await analytics.log_slot_booked(
        user_id=candidate.telegram_id or candidate.telegram_user_id or candidate.id,
        candidate_id=candidate.id,
        slot_id=reserved_slot.id if reserved_slot else slot_id,
        booking_id=reserved_slot.id if reserved_slot else slot_id,
        city_id=reserved_slot.city_id if reserved_slot else city.id,
        metadata={"source": "candidate_portal"},
    )
    return serialize_portal_slot(reserved_slot) if reserved_slot else {"id": slot_id}


async def confirm_candidate_portal_slot(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
) -> dict[str, Any]:
    active_slot = await get_candidate_active_slot(session, candidate)
    if active_slot is None:
        raise CandidatePortalError("Активный слот не найден.")

    slot = active_slot
    if _dialect_name(session) == "sqlite":
        status_value = (active_slot.status or "").lower()
        if status_value in {SlotStatus.CONFIRMED, SlotStatus.CONFIRMED_BY_CANDIDATE}:
            slot = active_slot
        elif status_value not in {SlotStatus.PENDING, SlotStatus.BOOKED}:
            raise CandidatePortalError("Слот нельзя подтвердить в текущем статусе.")
        else:
            active_slot.status = SlotStatus.CONFIRMED_BY_CANDIDATE
            slot = active_slot
            await session.flush()
    else:
        result = await confirm_slot_by_candidate(active_slot.id)
        slot = result.slot if result and result.slot is not None else active_slot
        if result.status not in {"already_confirmed", "confirmed"}:
            raise CandidatePortalError("Слот нельзя подтвердить в текущем статусе.")

    await ensure_candidate_slot_confirmed(session, candidate)
    await upsert_step_state(
        session,
        journey,
        step_key="status",
        step_type="status",
        status=CandidateJourneyStepStatus.IN_PROGRESS.value,
        payload={"slot_id": slot.id, "action": "confirm"},
    )
    await analytics.log_funnel_event(
        analytics.FunnelEvent.SLOT_CONFIRMED,
        user_id=candidate.telegram_id or candidate.telegram_user_id,
        candidate_id=candidate.id,
        slot_id=slot.id,
        booking_id=slot.id,
        metadata={"source": "candidate_portal"},
        session=session,
    )
    return serialize_portal_slot(slot)


async def cancel_candidate_portal_slot(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
) -> dict[str, Any]:
    active_slot = await get_candidate_active_slot(session, candidate)
    if active_slot is None:
        raise CandidatePortalError("Активный слот не найден.")

    released_slot_id = active_slot.id
    if _dialect_name(session) == "sqlite":
        active_slot.status = SlotStatus.FREE
        active_slot.candidate_id = None
        active_slot.candidate_tg_id = None
        active_slot.candidate_fio = None
        active_slot.candidate_tz = None
        active_slot.candidate_city_id = None
        active_slot.purpose = "interview"
        await session.flush()
    else:
        await reject_slot(released_slot_id)
    await ensure_candidate_waiting_slot(session, candidate)
    await upsert_step_state(
        session,
        journey,
        step_key="slot_selection",
        step_type="schedule",
        status=CandidateJourneyStepStatus.IN_PROGRESS.value,
        payload={"released_slot_id": released_slot_id, "action": "cancel"},
    )
    await analytics.log_slot_canceled(
        user_id=candidate.telegram_id or candidate.telegram_user_id or candidate.id,
        candidate_id=candidate.id,
        booking_id=released_slot_id,
        slot_id=released_slot_id,
        reason="candidate_portal_cancel",
        metadata={"source": "candidate_portal"},
    )
    return {"released_slot_id": released_slot_id}


async def reschedule_candidate_portal_slot(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
    *,
    new_slot_id: int,
) -> dict[str, Any]:
    active_slot = await get_candidate_active_slot(session, candidate)
    if active_slot is None:
        raise CandidatePortalError("Текущий слот не найден.")

    city = await _resolve_city(session, city_name=candidate.city)
    if city is None:
        raise CandidatePortalError("Сначала укажите город кандидата.")

    replacement = await session.scalar(
        select(Slot)
        .options(selectinload(Slot.recruiter), selectinload(Slot.city))
        .where(Slot.id == new_slot_id)
        .with_for_update()
    )
    if replacement is None:
        raise CandidatePortalError("Новый слот не найден.")
    if (replacement.status or "").lower() != SlotStatus.FREE:
        raise CandidatePortalError("Новый слот уже занят.")
    if replacement.id == active_slot.id:
        raise CandidatePortalError("Выберите другой слот для переноса.")

    old_slot_id = active_slot.id
    if _dialect_name(session) == "sqlite":
        active_slot.status = SlotStatus.FREE
        active_slot.candidate_id = None
        active_slot.candidate_tg_id = None
        active_slot.candidate_fio = None
        active_slot.candidate_tz = None
        active_slot.candidate_city_id = None
        active_slot.purpose = "interview"
        replacement.status = SlotStatus.PENDING
        replacement.candidate_id = candidate.candidate_id
        replacement.candidate_tg_id = candidate.telegram_user_id or candidate.telegram_id
        replacement.candidate_fio = candidate.fio
        replacement.candidate_tz = resolve_candidate_timezone(city=city, candidate=candidate)
        replacement.candidate_city_id = city.id
        replacement.purpose = "interview"
        await session.flush()
    else:
        await reject_slot(old_slot_id)
        replacement.status = SlotStatus.PENDING
        replacement.candidate_id = candidate.candidate_id
        replacement.candidate_tg_id = candidate.telegram_user_id or candidate.telegram_id
        replacement.candidate_fio = candidate.fio
        replacement.candidate_tz = resolve_candidate_timezone(city=city, candidate=candidate)
        replacement.candidate_city_id = city.id
        replacement.purpose = "interview"

    candidate.responsible_recruiter_id = replacement.recruiter_id
    await ensure_candidate_slot_pending(session, candidate)
    await upsert_step_state(
        session,
        journey,
        step_key="slot_selection",
        step_type="schedule",
        status=CandidateJourneyStepStatus.COMPLETED.value,
        payload={"slot_id": replacement.id, "previous_slot_id": old_slot_id, "action": "reschedule"},
    )
    await analytics.log_slot_rescheduled(
        user_id=candidate.telegram_id or candidate.telegram_user_id or candidate.id,
        candidate_id=candidate.id,
        old_booking_id=old_slot_id,
        new_booking_id=replacement.id,
        new_slot_id=replacement.id,
        metadata={"source": "candidate_portal"},
    )
    return serialize_portal_slot(replacement)
