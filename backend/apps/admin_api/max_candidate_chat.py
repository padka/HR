"""Bounded MAX candidate chat orchestration over shared candidate-access state."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.admin_api.candidate_access.auth import (
    MAX_ACCESS_SESSION_IDLE_TTL,
    CandidateAccessPrincipal,
)
from backend.apps.admin_api.candidate_access.services import (
    CandidateBookingContextEnvelope,
    CandidateTest1Envelope,
    cancel_candidate_booking,
    complete_candidate_test1,
    confirm_candidate_booking,
    confirm_candidate_intro_day,
    create_candidate_booking,
    list_available_interview_slots,
    list_candidate_booking_cities,
    list_candidate_booking_recruiters,
    load_candidate_booking_context,
    load_candidate_intro_day,
    load_candidate_journey,
    load_candidate_test1_state,
    load_candidate_test2_state,
    reschedule_candidate_booking,
    save_candidate_booking_context,
    save_candidate_test1_answers,
    slot_duration_minutes,
    submit_candidate_test2_answer,
)
from backend.apps.admin_api.max_launch import (
    bootstrap_max_global_intake_token,
)
from backend.core.db import async_session
from backend.core.messenger.bootstrap import ensure_max_adapter
from backend.core.messenger.protocol import InlineButton
from backend.core.settings import Settings
from backend.domain.candidates.models import (
    CandidateAccessAuthMethod,
    CandidateAccessSession,
    CandidateAccessSessionStatus,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneySession,
    CandidateJourneySessionStatus,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    User,
)
from backend.domain.candidates.services import log_outbound_max_message
from backend.domain.candidates.test1_shared import (
    BOOKING_STEP_KEY,
    NEXT_ACTION_ASK_CANDIDATE,
    NEXT_ACTION_HOLD,
    NEXT_ACTION_HUMAN_DECLINE_REVIEW,
    NEXT_ACTION_SELECT_INTERVIEW_SLOT,
)
from backend.domain.models import Slot
from backend.domain.repositories import confirm_slot_by_candidate, reject_slot

MAX_CHAT_SURFACE = "max_chat"
_CHAT_CURSOR_KEY = "chat_cursor"
_CANDIDATE_ACCESS_KEY = "candidate_access"
_CHAT_START_PHRASES = (
    "пройти в чате",
    "продолжить в чате",
    "начать в чате",
    "хочу пройти в чате",
    "чат",
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MaxChatPrompt:
    text: str
    buttons: list[list[InlineButton]]
    state: str
    booking_id: int | None = None
    handoff_sent: bool = False


@dataclass(frozen=True, slots=True)
class MaxChatContext:
    candidate: User
    principal: CandidateAccessPrincipal
    journey_session: CandidateJourneySession


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _candidate_access_payload(journey_session: CandidateJourneySession) -> dict[str, Any]:
    payload = dict(journey_session.payload_json or {})
    return dict(payload.get(_CANDIDATE_ACCESS_KEY) or {})


def _set_chat_cursor(
    journey_session: CandidateJourneySession,
    *,
    state: str,
    booking_id: int | None = None,
    surface: str = MAX_CHAT_SURFACE,
) -> None:
    payload = dict(journey_session.payload_json or {})
    candidate_access = dict(payload.get(_CANDIDATE_ACCESS_KEY) or {})
    candidate_access["active_surface"] = surface
    candidate_access[_CHAT_CURSOR_KEY] = {
        "version": 1,
        "surface": surface,
        "state": state,
        "booking_id": booking_id,
        "updated_at": _utcnow().isoformat(),
    }
    payload[_CANDIDATE_ACCESS_KEY] = candidate_access
    journey_session.payload_json = payload
    journey_session.last_surface = surface
    journey_session.last_activity_at = _utcnow()


def wants_max_chat_handoff(text: str | None) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    return any(phrase in normalized for phrase in _CHAT_START_PHRASES)


async def resolve_max_chat_context(
    session: AsyncSession,
    *,
    max_user_id: str,
) -> MaxChatContext | None:
    normalized = str(max_user_id or "").strip()
    if not normalized:
        return None

    candidate = await session.scalar(select(User).where(User.max_user_id == normalized))
    if candidate is None or not candidate.is_active:
        return None

    now = _utcnow()
    access_session = await session.scalar(
        select(CandidateAccessSession)
        .where(
            CandidateAccessSession.candidate_id == candidate.id,
            CandidateAccessSession.provider_user_id == normalized,
            CandidateAccessSession.launch_channel == CandidateLaunchChannel.MAX.value,
            CandidateAccessSession.auth_method.in_(
                [
                    CandidateAccessAuthMethod.MAX_INIT_DATA.value,
                    CandidateAccessAuthMethod.ADMIN_INVITE.value,
                ]
            ),
            CandidateAccessSession.journey_surface.in_(
                [
                    CandidateJourneySurface.MAX_MINIAPP.value,
                    CandidateJourneySurface.MAX_CHAT.value,
                ]
            ),
            CandidateAccessSession.status == CandidateAccessSessionStatus.ACTIVE.value,
            CandidateAccessSession.revoked_at.is_(None),
            CandidateAccessSession.expires_at > now,
        )
        .order_by(
            CandidateAccessSession.last_seen_at.desc().nullslast(),
            CandidateAccessSession.id.desc(),
        )
        .limit(1)
    )
    if access_session is None:
        return None

    journey_session = await session.get(CandidateJourneySession, access_session.journey_session_id)
    if journey_session is None or journey_session.candidate_id != candidate.id:
        return None
    if int(access_session.session_version_snapshot or 0) != int(journey_session.session_version or 0):
        return None

    access_session.last_seen_at = now
    access_session.refreshed_at = now
    access_session.expires_at = now + MAX_ACCESS_SESSION_IDLE_TTL
    journey_session.last_access_session_id = access_session.id
    journey_session.last_activity_at = now

    principal = CandidateAccessPrincipal(
        candidate_id=int(candidate.id),
        application_id=access_session.application_id,
        access_session_id=int(access_session.id),
        surface=MAX_CHAT_SURFACE,
        provider=CandidateLaunchChannel.MAX.value,
        provider_user_id=normalized,
        auth_method=access_session.auth_method,
        session_status=access_session.status,
        correlation_id=access_session.correlation_id,
        journey_session_id=int(journey_session.id),
        session_version_snapshot=int(access_session.session_version_snapshot or 0),
    )
    return MaxChatContext(candidate=candidate, principal=principal, journey_session=journey_session)


async def _load_active_start_token(
    session: AsyncSession,
    *,
    start_param: str,
    now: datetime,
) -> CandidateAccessToken | None:
    normalized = str(start_param or "").strip()
    if not normalized:
        return None
    return await session.scalar(
        select(CandidateAccessToken)
        .where(
            CandidateAccessToken.start_param == normalized,
            CandidateAccessToken.token_kind.in_(
                [
                    CandidateAccessTokenKind.INVITE.value,
                    CandidateAccessTokenKind.LAUNCH.value,
                    CandidateAccessTokenKind.RESUME.value,
                ]
            ),
            CandidateAccessToken.launch_channel == CandidateLaunchChannel.MAX.value,
            CandidateAccessToken.revoked_at.is_(None),
            CandidateAccessToken.expires_at > now,
        )
        .order_by(CandidateAccessToken.created_at.desc(), CandidateAccessToken.id.desc())
        .limit(1)
        .with_for_update()
    )


async def _ensure_chat_journey_session(
    session: AsyncSession,
    *,
    token: CandidateAccessToken,
    now: datetime,
) -> CandidateJourneySession:
    journey_session: CandidateJourneySession | None = None
    if token.journey_session_id is not None:
        journey_session = await session.get(CandidateJourneySession, token.journey_session_id)
        if journey_session is not None and journey_session.candidate_id != token.candidate_id:
            journey_session = None

    if journey_session is None:
        journey_session = CandidateJourneySession(
            candidate_id=token.candidate_id,
            application_id=token.application_id,
            entry_channel=CandidateLaunchChannel.MAX.value,
            last_surface=MAX_CHAT_SURFACE,
            last_auth_method=CandidateAccessAuthMethod.ADMIN_INVITE.value,
            last_activity_at=now,
        )
        session.add(journey_session)
        await session.flush()
        token.journey_session_id = journey_session.id

    return journey_session


async def _load_existing_direct_chat_session(
    session: AsyncSession,
    *,
    provider_user_id: str,
    provider_session_id: str,
    now: datetime,
) -> CandidateAccessSession | None:
    return await session.scalar(
        select(CandidateAccessSession)
        .where(
            CandidateAccessSession.provider_user_id == provider_user_id,
            CandidateAccessSession.provider_session_id == provider_session_id,
            CandidateAccessSession.journey_surface == CandidateJourneySurface.MAX_CHAT.value,
            CandidateAccessSession.status == CandidateAccessSessionStatus.ACTIVE.value,
            CandidateAccessSession.expires_at > now,
        )
        .order_by(CandidateAccessSession.issued_at.desc(), CandidateAccessSession.id.desc())
        .limit(1)
    )


async def bootstrap_max_chat_principal(
    session: AsyncSession,
    *,
    max_user_id: str,
    start_param: str | None = None,
    settings: Settings | None = None,
    provider_session_id: str | None = None,
    display_name: str | None = None,
    username: str | None = None,
) -> CandidateAccessPrincipal | None:
    normalized_user_id = str(max_user_id or "").strip()
    normalized_start_param = str(start_param or "").strip()
    if not normalized_user_id:
        return None

    now = _utcnow()
    if normalized_start_param:
        token = await _load_active_start_token(
            session,
            start_param=normalized_start_param,
            now=now,
        )
    else:
        if settings is None:
            return None
        token = await bootstrap_max_global_intake_token(
            session,
            settings=settings,
            provider_user_id=normalized_user_id,
            candidate_name=display_name,
            username=username,
            now=now,
        )
    if token is None:
        return None

    candidate = await session.get(User, int(token.candidate_id))
    if candidate is None or not candidate.is_active:
        return None
    candidate_max_user_id = str(getattr(candidate, "max_user_id", "") or "").strip()
    if not candidate_max_user_id or candidate_max_user_id != normalized_user_id:
        return None

    journey_session = await _ensure_chat_journey_session(session, token=token, now=now)
    provider_session_key = (
        str(provider_session_id or "").strip()
        or f"max-chat-start:{normalized_user_id}:{normalized_start_param}"
    )
    access_session = await _load_existing_direct_chat_session(
        session,
        provider_user_id=normalized_user_id,
        provider_session_id=provider_session_key,
        now=now,
    )
    if access_session is None:
        sqlite_session_id = None
        bind = session.get_bind()
        if bind is not None and bind.dialect.name == "sqlite":
            sqlite_session_id = int(
                await session.scalar(select(func.coalesce(func.max(CandidateAccessSession.id), 0) + 1))
                or 1
            )
        access_session = CandidateAccessSession(
            id=sqlite_session_id,
            candidate_id=int(candidate.id),
            application_id=token.application_id,
            journey_session_id=int(journey_session.id),
            origin_token_id=int(token.id),
            journey_surface=CandidateJourneySurface.MAX_CHAT.value,
            auth_method=CandidateAccessAuthMethod.ADMIN_INVITE.value,
            launch_channel=CandidateLaunchChannel.MAX.value,
            provider_session_id=provider_session_key,
            provider_user_id=normalized_user_id,
            session_version_snapshot=max(1, int(journey_session.session_version or 1)),
            phone_verification_state=token.phone_verification_state,
            phone_delivery_channel=token.phone_delivery_channel,
            status=CandidateAccessSessionStatus.ACTIVE.value,
            issued_at=now,
            last_seen_at=now,
            refreshed_at=now,
            expires_at=now + MAX_ACCESS_SESSION_IDLE_TTL,
            correlation_id=token.correlation_id or str(uuid.uuid4()),
            metadata_json={
                "bootstrapped_from": "max_bot_started",
                "start_param_bound": True,
            },
        )
        session.add(access_session)
        await session.flush()
    else:
        access_session.last_seen_at = now
        access_session.refreshed_at = now
        access_session.expires_at = now + MAX_ACCESS_SESSION_IDLE_TTL
        if access_session.origin_token_id is None:
            access_session.origin_token_id = int(token.id)

    token.provider_user_id = token.provider_user_id or normalized_user_id
    token.last_seen_at = now
    if token.session_version_snapshot is None:
        token.session_version_snapshot = max(1, int(journey_session.session_version or 1))

    journey_session.last_access_session_id = access_session.id
    journey_session.last_surface = MAX_CHAT_SURFACE
    journey_session.last_auth_method = access_session.auth_method
    journey_session.last_activity_at = now
    if journey_session.application_id is None and token.application_id is not None:
        journey_session.application_id = token.application_id
    if journey_session.status != CandidateJourneySessionStatus.ACTIVE.value:
        journey_session.status = CandidateJourneySessionStatus.ACTIVE.value

    return CandidateAccessPrincipal(
        candidate_id=int(candidate.id),
        application_id=access_session.application_id,
        access_session_id=int(access_session.id),
        surface=MAX_CHAT_SURFACE,
        provider=CandidateLaunchChannel.MAX.value,
        provider_user_id=normalized_user_id,
        auth_method=access_session.auth_method,
        session_status=access_session.status,
        correlation_id=access_session.correlation_id,
        journey_session_id=int(journey_session.id),
        session_version_snapshot=int(access_session.session_version_snapshot or 0),
    )


def _current_chat_cursor_state(journey_session: CandidateJourneySession) -> str | None:
    payload = _candidate_access_payload(journey_session)
    cursor = payload.get(_CHAT_CURSOR_KEY)
    if not isinstance(cursor, dict):
        return None
    if str(cursor.get("surface") or "").strip() != MAX_CHAT_SURFACE:
        return None
    return str(cursor.get("state") or "").strip() or None


def _format_slot_window(start_utc: datetime, duration_min: int, tz_name: str) -> str:
    zone = ZoneInfo(str(tz_name or "Europe/Moscow"))
    aware_start = _as_utc(start_utc) or _utcnow()
    local_start = aware_start.astimezone(zone)
    local_end = (aware_start + timedelta(minutes=duration_min)).astimezone(zone)
    return f"{local_start.strftime('%d %b, %H:%M')}–{local_end.strftime('%H:%M')}"


def _question_progress(envelope: CandidateTest1Envelope) -> tuple[dict[str, Any] | None, int, int]:
    total = len(envelope.questions)
    for index, question in enumerate(envelope.questions, start=1):
        if not str(envelope.draft_answers.get(str(question["id"]), "")).strip():
            return question, index, total
    return None, total, total


def _question_buttons(question: dict[str, Any]) -> list[list[InlineButton]]:
    rows: list[list[InlineButton]] = []
    for index, option in enumerate(list(question.get("options") or [])):
        rows.append(
            [
                InlineButton(
                    text=str(option.get("label") or option.get("value") or "Выбрать"),
                    callback_data=f"test1:{question['id']}:{index}",
                    kind="callback",
                )
            ]
        )
    return rows


def _booking_conflict_http_error(result_status: str) -> HTTPException:
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


def _build_question_prompt(
    envelope: CandidateTest1Envelope,
    *,
    intro: bool = False,
) -> MaxChatPrompt:
    question, index, total = _question_progress(envelope)
    if question is None:
        return MaxChatPrompt(
            text="Ответы сохранены. Завершаю анкету и готовлю следующий шаг…",
            buttons=[],
            state="test1_answering",
        )
    prefix = "Продолжим здесь.\n\n" if intro else ""
    helper = str(question.get("helper") or "").strip()
    options = list(question.get("options") or [])
    hint = (
        "Нажмите на вариант ниже."
        if options
        else str(question.get("placeholder") or "Напишите ответ одним сообщением.")
    )
    text = (
        f"{prefix}Шаг {index} из {total}\n"
        f"{question['prompt']}\n\n"
        f"{helper}\n{hint}"
    ).strip()
    return MaxChatPrompt(
        text=text,
        buttons=_question_buttons(question),
        state="test1_answering",
    )


def _friendly_completion_text(envelope: CandidateTest1Envelope) -> str:
    action = str(envelope.required_next_action or "").strip()
    if action == NEXT_ACTION_SELECT_INTERVIEW_SLOT:
        return "Спасибо. Опрос завершён, можно выбрать удобное время для интервью."
    if action == NEXT_ACTION_ASK_CANDIDATE:
        return "Спасибо. Ответы записаны, рекрутер уточнит детали и продолжит с вами в чате."
    if action == NEXT_ACTION_HOLD:
        return "Спасибо. Ответы получены. Мы вернёмся к вам, как только сможем предложить следующий шаг."
    if action == NEXT_ACTION_HUMAN_DECLINE_REVIEW:
        return "Спасибо. Результаты приняты, команда ещё раз их посмотрит и вернётся с ответом."
    return "Спасибо. Ответы приняты, рекрутер продолжит с вами следующий шаг."


async def _offer_slots_for_chat(
    session: AsyncSession,
    *,
    context: CandidateBookingContextEnvelope,
) -> list[Slot]:
    if context.city_id is None or context.recruiter_id is None:
        return []
    return await list_available_interview_slots(
        session,
        city_id=int(context.city_id),
        recruiter_id=int(context.recruiter_id),
        from_date=None,
        to_date=None,
    )


def _format_local_moment(start_utc: datetime | None, tz_name: str) -> str:
    if start_utc is None:
        return ""
    zone = ZoneInfo(str(tz_name or "Europe/Moscow"))
    aware_start = _as_utc(start_utc) or _utcnow()
    return aware_start.astimezone(zone).strftime("%d %b, %H:%M")


def _city_choice_buttons(
    cities: list,
    *,
    selected_city_id: int | None,
) -> list[list[InlineButton]]:
    rows: list[list[InlineButton]] = []
    for city in cities:
        prefix = "• " if selected_city_id is not None and int(city.city_id) == int(selected_city_id) else ""
        suffix = (
            f" · {city.available_recruiters} рекр. · {city.available_slots} сл."
            if city.has_available_recruiters
            else " · пока без слотов"
        )
        rows.append(
            [
                InlineButton(
                    text=f"{prefix}{city.city_name}{suffix}",
                    callback_data=f"city:pick:{city.city_id}",
                    kind="callback",
                )
            ]
        )
    rows.append([InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")])
    return rows


async def _build_city_prompt(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    intro: bool = False,
) -> MaxChatPrompt:
    envelope = await load_candidate_test1_state(session, principal)
    context = await load_candidate_booking_context(session, principal)
    cities = await list_candidate_booking_cities(session, principal)
    prefix = "Продолжим здесь.\n\n" if intro else ""
    if not cities:
        logger.info(
            "max.chat.no_cities_available",
            extra={
                "candidate_id": principal.candidate_id,
                "journey_session_id": principal.journey_session_id,
            },
        )
        return MaxChatPrompt(
            text=(
                f"{prefix}Пока не получилось загрузить города для записи. "
                "Напишите удобные дату и время на ближайшие 1–2 дня, и рекрутер свяжется с вами."
            ),
            buttons=[[InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")]],
            state="manual_time_input",
        )

    current_city = context.city_name or "город из анкеты"
    return MaxChatPrompt(
        text=(
            f"{prefix}{_friendly_completion_text(envelope)}\n\n"
            f"Сейчас выбран город: {current_city}.\n"
            "Нажмите на подходящий город, и я покажу доступных рекрутёров."
        ),
        buttons=_city_choice_buttons(cities, selected_city_id=context.city_id),
        state="booking_city",
    )


def _recruiter_choice_buttons(
    recruiters: list,
    *,
    candidate_tz: str,
) -> list[list[InlineButton]]:
    rows: list[list[InlineButton]] = []
    for recruiter in recruiters:
        next_slot = _format_local_moment(recruiter.next_slot_utc, candidate_tz)
        suffix = f" · {next_slot}" if next_slot else ""
        rows.append(
            [
                InlineButton(
                    text=f"{recruiter.recruiter_name} · {recruiter.available_slots} сл.{suffix}",
                    callback_data=f"recruiter:pick:{recruiter.recruiter_id}",
                    kind="callback",
                )
            ]
        )
    rows.append([InlineButton(text="Другой город", callback_data="booking:change_city", kind="callback")])
    rows.append([InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")])
    return rows


async def _build_recruiter_prompt(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    intro: bool = False,
) -> MaxChatPrompt:
    context = await load_candidate_booking_context(session, principal)
    prefix = "Продолжим здесь.\n\n" if intro else ""
    if context.city_id is None:
        return await _build_city_prompt(session, principal, intro=intro)

    recruiters = await list_candidate_booking_recruiters(session, principal, city_id=int(context.city_id))
    if not recruiters:
        logger.info(
            "max.chat.no_recruiters_available",
            extra={
                "candidate_id": principal.candidate_id,
                "journey_session_id": principal.journey_session_id,
                "city_id": context.city_id,
            },
        )
        return MaxChatPrompt(
            text=(
                f"{prefix}Для города {context.city_name or 'из анкеты'} пока нет свободных слотов у рекрутёров. "
                "Можно выбрать другой город или написать удобные дату и время на ближайшие 1–2 дня."
            ),
            buttons=[
                [InlineButton(text="Другой город", callback_data="booking:change_city", kind="callback")],
                [InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")],
            ],
            state="booking_recruiter",
        )

    return MaxChatPrompt(
        text=(
            f"{prefix}Город: {context.city_name or '—'}\n\n"
            "Выберите рекрутёра, и я покажу его ближайшее доступное время."
        ),
        buttons=_recruiter_choice_buttons(recruiters, candidate_tz=context.profile.timezone_name),
        state="booking_recruiter",
    )


def _slot_choice_buttons(
    slots: list[Slot],
    *,
    booking_id: int | None = None,
) -> list[list[InlineButton]]:
    rows: list[list[InlineButton]] = []
    prefix = "slot:reschedule_pick" if booking_id is not None else "slot:book"
    for slot in slots[:6]:
        rows.append(
            [
                InlineButton(
                    text=f"Выбрать {slot.start_utc.strftime('%d.%m %H:%M')}",
                    callback_data=(
                        f"{prefix}:{booking_id}:{slot.id}"
                        if booking_id is not None
                        else f"{prefix}:{slot.id}"
                    ),
                    kind="callback",
                )
            ]
        )
    rows.append([InlineButton(text="Другой рекрутёр", callback_data="booking:change_recruiter", kind="callback")])
    rows.append([InlineButton(text="Другой город", callback_data="booking:change_city", kind="callback")])
    rows.append([InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")])
    return rows


async def _build_slot_prompt(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    envelope: CandidateTest1Envelope,
    context: CandidateBookingContextEnvelope,
    *,
    intro: bool = False,
    booking_id: int | None = None,
) -> MaxChatPrompt:
    if context.recruiter_id is None:
        return await _build_recruiter_prompt(session, principal, intro=intro)

    slots = await _offer_slots_for_chat(session, context=context)
    prefix = "Продолжим здесь.\n\n" if intro else ""
    city_label = context.city_name or "выбранный город"
    recruiter_label = context.recruiter_name or "выбранный рекрутёр"
    if not slots:
        logger.info(
            "max.chat.no_slots_available",
            extra={
                "candidate_id": principal.candidate_id,
                "journey_session_id": principal.journey_session_id,
                "city_id": context.city_id,
                "recruiter_id": context.recruiter_id,
            },
        )
        return MaxChatPrompt(
            text=(
                f"{prefix}Для города {city_label} у {recruiter_label} пока нет свободных слотов. "
                "Можно выбрать другого рекрутёра, другой город или написать удобные дату и время."
            ),
            buttons=[
                [InlineButton(text="Другой рекрутёр", callback_data="booking:change_recruiter", kind="callback")],
                [InlineButton(text="Другой город", callback_data="booking:change_city", kind="callback")],
                [InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")],
            ],
            state="booking_selecting",
            booking_id=booking_id,
        )

    lines = [
        f"{prefix}{_friendly_completion_text(envelope)}",
        "",
        f"Город: {city_label}",
        f"Рекрутёр: {recruiter_label}",
        "",
        "Ближайшие варианты:",
    ]
    tz_name = envelope.profile.timezone_name
    for index, slot in enumerate(slots[:6], start=1):
        lines.append(f"{index}. {_format_slot_window(slot.start_utc, slot_duration_minutes(slot), tz_name)}")
    lines.append("")
    lines.append("Выберите новый слот ниже." if booking_id is not None else "Выберите удобный вариант ниже.")

    return MaxChatPrompt(
        text="\n".join(lines).strip(),
        buttons=_slot_choice_buttons(slots, booking_id=booking_id),
        state="booking_rescheduling" if booking_id is not None else "booking_selecting",
        booking_id=booking_id,
    )


def _booking_summary_prompt(slot: Slot) -> MaxChatPrompt:
    tz_name = getattr(slot, "candidate_tz", None) or getattr(slot, "tz_name", None) or "Europe/Moscow"
    recruiter = getattr(getattr(slot, "recruiter", None), "name", None) or "Рекрутер RecruitSmart"
    text = (
        "Запись готова.\n\n"
        f"{_format_slot_window(slot.start_utc, slot_duration_minutes(slot), str(tz_name))} · {recruiter}\n\n"
        "Подтвердите слот или выберите другое время."
    )
    buttons = [
        [InlineButton(text="Подтвердить", callback_data=f"slot:confirm:{slot.id}", kind="callback")],
        [InlineButton(text="Выбрать другое время", callback_data=f"slot:reschedule:{slot.id}", kind="callback")],
        [InlineButton(text="Отменить запись", callback_data=f"slot:cancel:{slot.id}", kind="callback")],
        [InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")],
    ]
    return MaxChatPrompt(text=text, buttons=buttons, state="booking_pending", booking_id=int(slot.id))


def _confirmed_booking_prompt(slot: Slot) -> MaxChatPrompt:
    tz_name = getattr(slot, "candidate_tz", None) or getattr(slot, "tz_name", None) or "Europe/Moscow"
    recruiter = getattr(getattr(slot, "recruiter", None), "name", None) or "Рекрутер RecruitSmart"
    text = (
        "Готово, встречу подтвердили.\n\n"
        f"{_format_slot_window(slot.start_utc, slot_duration_minutes(slot), str(tz_name))} · {recruiter}\n\n"
        "Если понадобится, здесь же можно выбрать другое время."
    )
    buttons = [
        [InlineButton(text="Выбрать другое время", callback_data=f"slot:reschedule:{slot.id}", kind="callback")],
        [InlineButton(text="Отменить запись", callback_data=f"slot:cancel:{slot.id}", kind="callback")],
    ]
    return MaxChatPrompt(text=text, buttons=buttons, state="booking_pending", booking_id=int(slot.id))


def _completion_only_prompt(envelope: CandidateTest1Envelope) -> MaxChatPrompt:
    return MaxChatPrompt(
        text=_friendly_completion_text(envelope),
        buttons=[],
        state="completed",
    )


def _build_test2_prompt(
    *,
    envelope,
    intro: bool = False,
) -> MaxChatPrompt:
    prefix = "Продолжим здесь.\n\n" if intro else ""
    if envelope.is_completed:
        text = envelope.result_message or (
            "Тест 2 завершён. Ожидайте следующий шаг RecruitSmart."
        )
        return MaxChatPrompt(
            text=f"{prefix}{text}".strip(),
            buttons=[],
            state="test2_completed",
        )

    if envelope.current_question_index is None:
        return MaxChatPrompt(
            text=(
                f"{prefix}Тест 2 уже открыт. Откройте mini app через кнопку в шапке чата "
                "или продолжите здесь, как только появится следующий вопрос."
            ).strip(),
            buttons=[],
            state="test2_ready",
        )

    question = envelope.questions[envelope.current_question_index]
    rows: list[list[InlineButton]] = []
    for option in list(question.get("options") or []):
        rows.append(
            [
                InlineButton(
                    text=str(option.get("label") or option.get("value") or "Выбрать"),
                    callback_data=(
                        f"test2:{question['question_index']}:{int(option['value'])}"
                    ),
                    kind="callback",
                )
            ]
        )
    text = (
        f"{prefix}Тест 2 · вопрос {int(question['question_index']) + 1}/{envelope.total_questions}\n\n"
        f"{question['prompt']}\n\n"
        "Выберите один вариант ответа."
    )
    return MaxChatPrompt(
        text=text.strip(),
        buttons=rows,
        state="test2_answering",
    )


def _build_intro_day_prompt(*, envelope, intro: bool = False) -> MaxChatPrompt:
    prefix = "Продолжим здесь.\n\n" if intro else ""
    slot = envelope.slot
    if slot is None:
        return MaxChatPrompt(
            text=f"{prefix}Ознакомительный день пока не назначен.".strip(),
            buttons=[],
            state="completed",
        )
    start_text = _format_slot_window(
        slot.start_utc,
        slot_duration_minutes(slot),
        str(getattr(slot, "candidate_tz", None) or envelope.profile.timezone_name),
    )
    lines = [
        f"{prefix}Ознакомительный день назначен.".strip(),
        "",
        start_text,
        f"Адрес: {envelope.intro_address or 'уточним в чате'}",
    ]
    contact_line = envelope.intro_contact or ", ".join(
        [item for item in [envelope.contact_name, envelope.contact_phone] if item]
    )
    if contact_line:
        lines.append(f"Контакт: {contact_line}")
    if envelope.recruiter_name:
        lines.append(f"Рекрутёр: {envelope.recruiter_name}")
    lines.append("")
    lines.append("Подтвердите участие или вернитесь в чат MAX, если нужно уточнить детали.")
    return MaxChatPrompt(
        text="\n".join(lines).strip(),
        buttons=[
            [InlineButton(text="Подтвердить участие", callback_data="intro_day:confirm", kind="callback")],
        ],
        state="intro_day_pending",
        booking_id=int(slot.id),
    )


async def build_max_chat_prompt(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    intro: bool = False,
    booking_id: int | None = None,
) -> MaxChatPrompt:
    envelope = await load_candidate_test1_state(session, principal)
    if not envelope.is_completed:
        return _build_question_prompt(envelope, intro=intro)

    journey = await load_candidate_journey(session, principal)
    candidate_status = str(getattr(journey.profile.candidate, "candidate_status", "") or "").strip().lower()
    if candidate_status in {"test2_sent", "test2_completed", "test2_failed"}:
        test2 = await load_candidate_test2_state(session, principal)
        return _build_test2_prompt(envelope=test2, intro=intro)
    if candidate_status.startswith("intro_day"):
        intro_day = await load_candidate_intro_day(session, principal)
        return _build_intro_day_prompt(envelope=intro_day, intro=intro)
    if journey.active_booking is not None:
        return _booking_summary_prompt(journey.active_booking)

    if (
        envelope.required_next_action == NEXT_ACTION_SELECT_INTERVIEW_SLOT
        or journey.journey_session.current_step_key == BOOKING_STEP_KEY
    ):
        context = await load_candidate_booking_context(session, principal)
        cursor_state = _current_chat_cursor_state(journey.journey_session)
        if cursor_state == "booking_city":
            return await _build_city_prompt(session, principal, intro=intro)
        if cursor_state == "booking_recruiter":
            return await _build_recruiter_prompt(session, principal, intro=intro)
        if cursor_state in {"booking_selecting", "booking_rescheduling"} or context.recruiter_id is not None:
            return await _build_slot_prompt(
                session,
                principal,
                envelope,
                context,
                intro=intro,
                booking_id=booking_id,
            )
        if not context.is_explicit:
            return await _build_city_prompt(session, principal, intro=intro)
        return await _build_recruiter_prompt(session, principal, intro=intro)

    return _completion_only_prompt(envelope)


async def activate_max_chat_handoff(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
) -> MaxChatPrompt:
    prompt = await build_max_chat_prompt(session, principal, intro=True)
    journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
    if journey_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")
    _set_chat_cursor(
        journey_session,
        state=prompt.state,
        booking_id=prompt.booking_id,
        surface=MAX_CHAT_SURFACE,
    )
    return MaxChatPrompt(
        text=prompt.text,
        buttons=prompt.buttons,
        state=prompt.state,
        booking_id=prompt.booking_id,
        handoff_sent=True,
    )


async def book_max_chat_slot(
    principal: CandidateAccessPrincipal,
    *,
    slot_id: int,
) -> MaxChatPrompt:
    async with async_session() as session:
        async with session.begin():
            _, slot = await create_candidate_booking(session, principal, slot_id=slot_id)
            journey_session = await session.get(
                CandidateJourneySession,
                principal.journey_session_id,
                with_for_update=True,
            )
            if journey_session is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")
            prompt = _booking_summary_prompt(slot)
            _set_chat_cursor(journey_session, state=prompt.state, booking_id=prompt.booking_id)
            return prompt


async def send_max_chat_prompt(
    *,
    settings: Settings,
    max_user_id: str,
    prompt: MaxChatPrompt,
    client_request_id: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    adapter = await ensure_max_adapter(settings=settings)
    if adapter is None:
        return False
    result = await adapter.send_message(max_user_id, prompt.text, buttons=prompt.buttons or None)
    if not result.success:
        return False
    await log_outbound_max_message(
        max_user_id,
        text=prompt.text,
        payload={
            "origin_channel": "max",
            "kind": "candidate_chat_prompt",
            "state": prompt.state,
            **dict(payload or {}),
        },
        provider_message_id=result.message_id,
        client_request_id=client_request_id,
    )
    return True


async def process_max_chat_text_answer(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    text: str,
) -> MaxChatPrompt:
    current = await load_candidate_test1_state(session, principal)
    if current.is_completed:
        return await build_max_chat_prompt(session, principal)

    question, _, _ = _question_progress(current)
    if question is None:
        completion = await complete_candidate_test1(session, principal)
        if completion.required_next_action == NEXT_ACTION_SELECT_INTERVIEW_SLOT:
            prompt = await build_max_chat_prompt(session, principal)
        else:
            prompt = _completion_only_prompt(completion)
    else:
        try:
            updated = await save_candidate_test1_answers(
                session,
                principal,
                answers={str(question["id"]): text},
            )
        except HTTPException as exc:
            message = str(exc.detail or "Не получилось сохранить ответ.")
            prompt = _build_question_prompt(current)
            prompt = MaxChatPrompt(
                text=f"{message}\n\n{prompt.text}",
                buttons=prompt.buttons,
                state=prompt.state,
            )
        else:
            next_question, _, _ = _question_progress(updated)
            if next_question is None:
                completion = await complete_candidate_test1(session, principal)
                if completion.required_next_action == NEXT_ACTION_SELECT_INTERVIEW_SLOT:
                    prompt = await build_max_chat_prompt(session, principal)
                else:
                    prompt = _completion_only_prompt(completion)
            else:
                prompt = _build_question_prompt(updated)

    journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
    if journey_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")
    _set_chat_cursor(journey_session, state=prompt.state, booking_id=prompt.booking_id)
    return prompt


async def process_max_chat_callback(
    session: AsyncSession,
    principal: CandidateAccessPrincipal,
    *,
    callback_payload: str,
) -> MaxChatPrompt | None:
    if callback_payload == "test2:start":
        envelope = await load_candidate_test2_state(session, principal)
        prompt = _build_test2_prompt(envelope=envelope, intro=True)
        journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
        if journey_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")
        _set_chat_cursor(journey_session, state=prompt.state, booking_id=prompt.booking_id)
        return prompt

    if callback_payload.startswith("test1:"):
        parts = callback_payload.split(":")
        if len(parts) != 3:
            return None
        _, qid, raw_index = parts
        current = await load_candidate_test1_state(session, principal)
        question, _, _ = _question_progress(current)
        if question is None or str(question["id"]) != qid:
            prompt = _build_question_prompt(current)
        else:
            try:
                option = list(question.get("options") or [])[int(raw_index)]
                answer = str(option.get("value") or option.get("label") or "")
            except (IndexError, ValueError, TypeError):
                return None
            prompt = await process_max_chat_text_answer(session, principal, text=answer)
        return prompt

    if callback_payload.startswith("test2:"):
        parts = callback_payload.split(":")
        if len(parts) != 3:
            return None
        _, raw_question_index, raw_answer_index = parts
        try:
            question_index = int(raw_question_index)
            answer_index = int(raw_answer_index)
        except (TypeError, ValueError):
            return None
        envelope = await submit_candidate_test2_answer(
            session,
            principal,
            question_index=question_index,
            answer_index=answer_index,
        )
        prompt = _build_test2_prompt(envelope=envelope)
        journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
        if journey_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")
        _set_chat_cursor(journey_session, state=prompt.state, booking_id=prompt.booking_id)
        return prompt

    if callback_payload.startswith("slot:book:"):
        return None
    elif callback_payload.startswith("city:pick:"):
        try:
            city_id = int(callback_payload.split(":", 2)[2])
        except (IndexError, TypeError, ValueError):
            return None
        await save_candidate_booking_context(session, principal, city_id=city_id, recruiter_id=None)
        prompt = await _build_recruiter_prompt(session, principal)
    elif callback_payload == "booking:change_city":
        journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
        if journey_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")
        _set_chat_cursor(journey_session, state="booking_city")
        prompt = await _build_city_prompt(session, principal)
    elif callback_payload.startswith("recruiter:pick:"):
        try:
            recruiter_id = int(callback_payload.split(":", 2)[2])
        except (IndexError, TypeError, ValueError):
            return None
        context = await load_candidate_booking_context(session, principal)
        if context.city_id is None:
            prompt = await _build_city_prompt(session, principal)
        else:
            await save_candidate_booking_context(
                session,
                principal,
                city_id=int(context.city_id),
                recruiter_id=recruiter_id,
            )
            envelope = await load_candidate_test1_state(session, principal)
            new_context = await load_candidate_booking_context(session, principal)
            prompt = await _build_slot_prompt(session, principal, envelope, new_context)
    elif callback_payload == "booking:change_recruiter":
        context = await load_candidate_booking_context(session, principal)
        if context.city_id is None:
            prompt = await _build_city_prompt(session, principal)
        else:
            await save_candidate_booking_context(
                session,
                principal,
                city_id=int(context.city_id),
                recruiter_id=None,
            )
            prompt = await _build_recruiter_prompt(session, principal)
    elif callback_payload.startswith("slot:confirm:"):
        booking_id = int(callback_payload.split(":", 2)[2])
        slot = await confirm_candidate_booking(session, principal, booking_id=booking_id)
        prompt = _confirmed_booking_prompt(slot)
    elif callback_payload.startswith("slot:reschedule_pick:"):
        _, _, raw_booking_id, raw_slot_id = callback_payload.split(":", 3)
        candidate, slot = await reschedule_candidate_booking(
            session,
            principal,
            booking_id=int(raw_booking_id),
            new_slot_id=int(raw_slot_id),
        )
        del candidate
        prompt = _booking_summary_prompt(slot)
    elif callback_payload.startswith("slot:reschedule:"):
        booking_id = int(callback_payload.split(":", 2)[2])
        envelope = await load_candidate_test1_state(session, principal)
        context = await load_candidate_booking_context(session, principal)
        prompt = await _build_slot_prompt(session, principal, envelope, context, booking_id=booking_id)
    elif callback_payload.startswith("slot:cancel:"):
        booking_id = int(callback_payload.split(":", 2)[2])
        await cancel_candidate_booking(session, principal, booking_id=booking_id)
        prompt = MaxChatPrompt(
            text="Запись отменили. Когда будете готовы продолжить, откройте приложение в MAX или напишите удобные дату и время.",
            buttons=[[InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")]],
            state="completed",
        )
    elif callback_payload == "intro_day:confirm":
        envelope = await confirm_candidate_intro_day(session, principal)
        prompt = MaxChatPrompt(
            text=(
                "Готово, участие подтверждено.\n\n"
                "Если детали встречи изменятся, мы обновим их здесь и в чате MAX."
            ),
            buttons=[],
            state="intro_day_confirmed",
            booking_id=int(envelope.slot.id) if envelope.slot is not None else None,
        )
    elif callback_payload.startswith("att_yes:"):
        try:
            slot_id = int(callback_payload.split(":", 1)[1])
        except (IndexError, TypeError, ValueError):
            return None
        result = await confirm_slot_by_candidate(
            slot_id,
            session=session,
            update_candidate_status=True,
        )
        if result.slot is None or result.status == "invalid_status":
            prompt = MaxChatPrompt(
                text="Эта заявка уже недоступна или ещё не подтверждена рекрутёром.",
                buttons=[],
                state="intro_day_pending",
            )
        else:
            prompt = MaxChatPrompt(
                text=(
                    "Готово, участие подтверждено.\n\n"
                    "Если детали встречи изменятся, мы обновим их здесь и в чате MAX."
                ),
                buttons=[],
                state="intro_day_confirmed",
                booking_id=int(result.slot.id),
            )
    elif callback_payload.startswith("att_no:"):
        try:
            slot_id = int(callback_payload.split(":", 1)[1])
        except (IndexError, TypeError, ValueError):
            return None
        slot = await reject_slot(
            slot_id,
            session=session,
            update_candidate_status=True,
        )
        if slot is None:
            prompt = MaxChatPrompt(
                text="Заявка уже обработана. Если нужен новый слот, продолжим в чате MAX.",
                buttons=[[InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")]],
                state="completed",
            )
        else:
            prompt = MaxChatPrompt(
                text=(
                    "Понял, участие отменили.\n\n"
                    "Если нужно подобрать новое время или уточнить следующий шаг, продолжим в чате MAX."
                ),
                buttons=[[InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")]],
                state="completed",
            )
    else:
        return None

    journey_session = await session.get(CandidateJourneySession, principal.journey_session_id)
    if journey_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journey session not found")
    _set_chat_cursor(journey_session, state=prompt.state, booking_id=prompt.booking_id)
    return prompt


def is_max_chat_active(journey_session: CandidateJourneySession | None) -> bool:
    if journey_session is None:
        return False
    return str(journey_session.last_surface or "").strip() == MAX_CHAT_SURFACE or (
        _current_chat_cursor_state(journey_session) is not None
    )


__all__ = [
    "MAX_CHAT_SURFACE",
    "MaxChatContext",
    "MaxChatPrompt",
    "activate_max_chat_handoff",
    "bootstrap_max_chat_principal",
    "build_max_chat_prompt",
    "is_max_chat_active",
    "process_max_chat_callback",
    "process_max_chat_text_answer",
    "resolve_max_chat_context",
    "send_max_chat_prompt",
    "wants_max_chat_handoff",
]
