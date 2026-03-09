"""Candidate-facing MAX bot flow built on top of the universal journey layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import html
import logging
import re
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.bot.city_registry import find_candidate_city_by_name, list_candidate_cities
from backend.apps.bot.test1_validation import apply_partial_validation
from backend.core.db import async_session
import backend.core.messenger.registry as messenger_registry
from backend.core.messenger.protocol import InlineButton, MessengerPlatform
from backend.domain import analytics
from backend.domain.candidate_status_service import CandidateStatusService
from backend.domain.candidates.models import (
    CandidateChatRead,
    CandidateJourneySession,
    CandidateJourneyStepState,
    CandidateJourneyStepStatus,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    InterviewNote,
    TestResult,
    User,
)
from backend.domain.candidates.portal_service import (
    CandidatePortalError,
    build_candidate_portal_journey,
    complete_screening,
    ensure_candidate_portal_session,
    get_candidate_portal_questions,
    save_candidate_profile,
    save_screening_draft,
    upsert_step_state,
)
from backend.domain.candidates.status import CandidateStatus

logger = logging.getLogger(__name__)

WELCOME_CALLBACK = "maxflow:start"
PORTAL_CALLBACK = "maxflow:portal"
QUESTION_CALLBACK_PREFIX = "mxq:"
PROFILE_PROMPTS = {
    "fio": (
        "Напишите, пожалуйста, ваше <b>ФИО</b> полностью.\n"
        "Пример: <i>Иванов Иван Иванович</i>"
    ),
    "phone": (
        "Укажите номер телефона в формате <b>+7XXXXXXXXXX</b>.\n"
        "Он нужен, чтобы рекрутер мог связаться с вами напрямую."
    ),
    "city": "Напишите город, в котором вам удобно пройти собеседование.",
}
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_status_service = CandidateStatusService()


@dataclass(frozen=True)
class OutboundMessage:
    text: str
    buttons: list[list[InlineButton]] | None = None
    parse_mode: str | None = "HTML"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _max_numeric_id(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def _candidate_uuid_from_payload(payload: str | None) -> str | None:
    clean = str(payload or "").strip()
    if not clean:
        return None
    if clean.startswith("candidate:"):
        clean = clean.split(":", 1)[1].strip()
    return clean if UUID_RE.fullmatch(clean) else None


def _question_buttons(question: dict[str, Any]) -> list[list[InlineButton]] | None:
    options = question.get("options") or []
    if not options:
        return None
    qid = str(question.get("id") or "").strip()
    if not qid:
        return None
    return [
        [InlineButton(text=str(option), callback_data=f"{QUESTION_CALLBACK_PREFIX}{qid}:{index}")]
        for index, option in enumerate(options)
    ]


def _normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        raise CandidatePortalError("Укажите телефон в формате +7XXXXXXXXXX.")
    return f"+{digits}"


def _is_placeholder_fio(value: str | None) -> bool:
    clean = str(value or "").strip()
    return not clean or clean.startswith("TG ") or clean.startswith("MAX ")


def _profile_draft(candidate: User, profile_state: CandidateJourneyStepState | None) -> dict[str, Any]:
    draft = dict(profile_state.payload_json or {}) if profile_state and profile_state.payload_json else {}
    if not draft.get("fio") and not _is_placeholder_fio(candidate.fio):
        draft["fio"] = candidate.fio
    if not draft.get("phone") and candidate.phone:
        draft["phone"] = candidate.phone
    if not draft.get("city_name") and candidate.city:
        draft["city_name"] = candidate.city
    return draft


def _next_profile_field(candidate: User, profile_state: CandidateJourneyStepState | None) -> str | None:
    draft = _profile_draft(candidate, profile_state)
    if not draft.get("fio"):
        return "fio"
    if not draft.get("phone"):
        return "phone"
    if not draft.get("city_id") and not draft.get("city_name"):
        return "city"
    return None


def _screening_question(answers: dict[str, Any]) -> dict[str, Any] | None:
    for question in get_candidate_portal_questions():
        qid = str(question["id"])
        if not str(answers.get(qid) or "").strip():
            return question
    return None


async def _merge_candidate_records(
    session: AsyncSession,
    *,
    source: User,
    target: User,
) -> None:
    if source.id == target.id:
        return

    await session.execute(
        update(TestResult).where(TestResult.user_id == source.id).values(user_id=target.id)
    )
    await session.execute(
        update(ChatMessage).where(ChatMessage.candidate_id == source.id).values(candidate_id=target.id)
    )
    await session.execute(
        update(InterviewNote).where(InterviewNote.user_id == source.id).values(user_id=target.id)
    )
    await session.execute(
        update(CandidateJourneySession)
        .where(CandidateJourneySession.candidate_id == source.id)
        .values(candidate_id=target.id)
    )
    await session.execute(
        update(CandidateChatRead)
        .where(CandidateChatRead.candidate_id == source.id)
        .values(candidate_id=target.id)
    )
    await session.delete(source)


async def _ensure_max_candidate(
    session: AsyncSession,
    *,
    max_user_id: str,
    display_name: str | None = None,
    start_payload: str | None = None,
) -> User:
    now = _utcnow()
    existing_by_max = await session.scalar(
        select(User)
        .where(User.max_user_id == max_user_id)
        .order_by(User.id.asc())
        .limit(1)
    )
    candidate_uuid = _candidate_uuid_from_payload(start_payload)
    candidate_from_payload = None
    if candidate_uuid:
        candidate_from_payload = await session.scalar(
            select(User).where(User.candidate_id == candidate_uuid)
        )

    candidate = candidate_from_payload or existing_by_max
    created = False

    if candidate_from_payload is not None and existing_by_max is not None and existing_by_max.id != candidate_from_payload.id:
        await _merge_candidate_records(session, source=existing_by_max, target=candidate_from_payload)

    if candidate is None:
        created = True
        candidate = User(
            fio=f"MAX {max_user_id}",
            last_activity=now,
            source="max_bot",
            messenger_platform="max",
            max_user_id=max_user_id,
            candidate_status=CandidateStatus.LEAD,
            status_changed_at=now,
            workflow_status="lead",
        )
        session.add(candidate)
        await session.flush()
        await analytics.log_funnel_event(
            analytics.FunnelEvent.BOT_ENTERED,
            user_id=_max_numeric_id(max_user_id),
            candidate_id=candidate.id,
            metadata={"channel": "max", "max_user_id": max_user_id},
            session=session,
        )

    candidate.max_user_id = max_user_id
    candidate.messenger_platform = "max"
    candidate.last_activity = now
    if not candidate.source:
        candidate.source = "max_bot"
    if candidate.candidate_status is None:
        await _status_service.force(candidate, CandidateStatus.LEAD, reason="max bot entry")

    await analytics.log_funnel_event(
        analytics.FunnelEvent.BOT_START,
        user_id=_max_numeric_id(max_user_id),
        candidate_id=candidate.id,
        metadata={"channel": "max", "max_user_id": max_user_id},
        session=session,
    )

    await session.flush()
    logger.info(
        "max_bot.candidate_resolved",
        extra={
            "candidate_id": candidate.id,
            "max_user_id": max_user_id,
            "candidate_created": created,
            "payload_linked": bool(candidate_uuid),
        },
    )
    return candidate


async def _render_status_message(
    session: AsyncSession,
    candidate: User,
) -> OutboundMessage:
    payload = await build_candidate_portal_journey(session, candidate, entry_channel="max")
    portal_url = payload["candidate"].get("portal_url")
    next_action = payload["journey"].get("next_action") or "Следующий шаг уже сохранён в вашем профиле."
    status_label = payload["candidate"].get("status_label") or "В обработке"
    active_slot = payload["journey"]["slots"].get("active")

    lines = [
        f"Ваш статус: <b>{html.escape(str(status_label))}</b>",
        html.escape(str(next_action)),
    ]
    if active_slot and active_slot.get("start_utc"):
        lines.append(f"Назначенный слот: <code>{html.escape(str(active_slot['start_utc']))}</code>")
    if portal_url:
        lines.append("")
        lines.append(f"Продолжить: {portal_url}")

    buttons = (
        [[InlineButton(text="Открыть кабинет кандидата", url=str(portal_url))]]
        if portal_url
        else None
    )
    return OutboundMessage(text="\n".join(lines), buttons=buttons)


async def _render_profile_prompt(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
) -> OutboundMessage:
    profile_state = next((item for item in journey.step_states if item.step_key == "profile"), None)
    field = _next_profile_field(candidate, profile_state)
    if field is None:
        return await _render_status_message(session, candidate)

    prompt = PROFILE_PROMPTS[field]
    if field == "city":
        cities = await list_candidate_cities()
        preview = ", ".join(city.display_name for city in cities[:8])
        if preview:
            prompt = f"{prompt}\n\nСейчас доступны города: <i>{html.escape(preview)}</i>"
    return OutboundMessage(text=prompt)


async def _ensure_screening_started(
    session: AsyncSession,
    *,
    candidate: User,
    journey: CandidateJourneySession,
) -> None:
    if journey.payload_json is None:
        journey.payload_json = {}
    if journey.payload_json.get("max_screening_started_logged_at"):
        return
    await analytics.log_funnel_event(
        analytics.FunnelEvent.TEST1_STARTED,
        user_id=_max_numeric_id(candidate.max_user_id or ""),
        candidate_id=candidate.id,
        metadata={"channel": "max"},
        session=session,
    )
    journey.payload_json["max_screening_started_logged_at"] = _utcnow().isoformat()
    await session.flush()


async def _render_screening_prompt(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
) -> OutboundMessage:
    screening_state = next((item for item in journey.step_states if item.step_key == "screening"), None)
    answers = dict(screening_state.payload_json or {}) if screening_state and screening_state.payload_json else {}
    question = _screening_question(answers)
    if question is None:
        return await _render_status_message(session, candidate)

    await _ensure_screening_started(session, candidate=candidate, journey=journey)
    prompt = str(question.get("prompt") or "")
    helper = str(question.get("helper") or "").strip()
    question_index = int(question.get("index") or 0)
    total = len(get_candidate_portal_questions())
    title = f"Вопрос {question_index}/{total}" if question_index else "Следующий вопрос"
    text = f"<b>{title}</b>\n\n{prompt}"
    if helper:
        text += f"\n\n<i>{helper}</i>"
    return OutboundMessage(text=text, buttons=_question_buttons(question))


async def _render_next_step(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
) -> list[OutboundMessage]:
    payload = await build_candidate_portal_journey(session, candidate, entry_channel="max")
    current_step = str(payload["journey"].get("current_step") or "")
    if current_step == "profile":
        return [await _render_profile_prompt(session, candidate, journey)]
    if current_step == "screening":
        messages: list[OutboundMessage] = []
        screening_payload = payload["journey"].get("screening") or {}
        if not (screening_payload.get("draft_answers") or {}):
            messages.append(
                OutboundMessage(
                    text="Контакты сохранены. Осталось ответить на короткую анкету.",
                )
            )
        messages.append(await _render_screening_prompt(session, candidate, journey))
        return messages
    if current_step in {"slot_selection", "status"}:
        return [
            OutboundMessage(
                text="Анкета сохранена. Следующий шаг доступен в кабинете кандидата.",
            ),
            await _render_status_message(session, candidate),
        ]
    return [await _render_status_message(session, candidate)]


async def _send_outbound(
    *,
    max_user_id: int | str,
    messages: list[OutboundMessage],
) -> None:
    adapter = messenger_registry.get_registry().get(MessengerPlatform.MAX)
    if adapter is None:
        raise RuntimeError("MAX adapter is not registered")
    for item in messages:
        await adapter.send_message(
            max_user_id,
            item.text,
            buttons=item.buttons,
            parse_mode=item.parse_mode,
        )


async def send_outbound(
    *,
    max_user_id: int | str,
    messages: list[OutboundMessage],
) -> None:
    try:
        await _send_outbound(max_user_id=max_user_id, messages=messages)
    except Exception:
        logger.exception("max_bot.send_failed", extra={"max_user_id": max_user_id})


async def _log_inbound_max_chat(
    session: AsyncSession,
    *,
    candidate: User,
    text: str,
    payload: dict[str, Any] | None = None,
) -> None:
    message = ChatMessage(
        candidate_id=candidate.id,
        telegram_user_id=None,
        direction=ChatMessageDirection.INBOUND.value,
        channel="max",
        text=text,
        payload_json=payload,
        status=ChatMessageStatus.RECEIVED.value,
        author_label="candidate_max",
    )
    candidate.last_activity = _utcnow()
    session.add(message)
    await session.flush()


async def _profile_answer(
    session: AsyncSession,
    *,
    candidate: User,
    journey: CandidateJourneySession,
    answer: str,
) -> list[OutboundMessage]:
    profile_state = next((item for item in journey.step_states if item.step_key == "profile"), None)
    field = _next_profile_field(candidate, profile_state)
    if field is None:
        return await _render_next_step(session, candidate, journey)

    draft = _profile_draft(candidate, profile_state)
    clean_answer = str(answer or "").strip()
    if not clean_answer:
        return [OutboundMessage(text="Нужен текстовый ответ."), await _render_profile_prompt(session, candidate, journey)]

    if field == "fio":
        try:
            apply_partial_validation({"fio": clean_answer})
        except Exception as exc:
            return [
                OutboundMessage(text=str(exc)),
                await _render_profile_prompt(session, candidate, journey),
            ]
        draft["fio"] = clean_answer
    elif field == "phone":
        try:
            draft["phone"] = _normalize_phone(clean_answer)
        except CandidatePortalError as exc:
            return [
                OutboundMessage(text=str(exc)),
                await _render_profile_prompt(session, candidate, journey),
            ]
    elif field == "city":
        city = await find_candidate_city_by_name(clean_answer)
        if city is None:
            suggestions = ", ".join(item.display_name for item in (await list_candidate_cities())[:6])
            text = "Город не найден. Напишите один из доступных городов."
            if suggestions:
                text += f"\n\nНапример: <i>{html.escape(suggestions)}</i>"
            return [
                OutboundMessage(text=text),
                await _render_profile_prompt(session, candidate, journey),
            ]
        draft["city_id"] = city.id
        draft["city_name"] = city.name_plain

    await upsert_step_state(
        session,
        journey,
        step_key="profile",
        status=CandidateJourneyStepStatus.IN_PROGRESS.value,
        payload=draft,
    )

    if draft.get("fio") and draft.get("phone") and draft.get("city_id"):
        await save_candidate_profile(
            session,
            candidate,
            journey,
            fio=str(draft["fio"]),
            phone=str(draft["phone"]),
            city_id=int(draft["city_id"]),
        )
    return await _render_next_step(session, candidate, journey)


def _match_option(question: dict[str, Any], answer: str) -> str | None:
    normalized = answer.strip().casefold()
    for option in question.get("options") or []:
        value = str(option).strip()
        if normalized == value.casefold():
            return value
    return None


async def _screening_answer(
    session: AsyncSession,
    *,
    candidate: User,
    journey: CandidateJourneySession,
    answer: str,
    forced_question_id: str | None = None,
) -> list[OutboundMessage]:
    screening_state = next((item for item in journey.step_states if item.step_key == "screening"), None)
    answers = dict(screening_state.payload_json or {}) if screening_state and screening_state.payload_json else {}
    question = _screening_question(answers)
    if question is None:
        return await _render_next_step(session, candidate, journey)

    qid = str(question.get("id") or "")
    if forced_question_id and forced_question_id != qid:
        return [
            OutboundMessage(text="Этот вопрос уже неактуален. Отправляю текущий шаг заново."),
            await _render_screening_prompt(session, candidate, journey),
        ]

    value = str(answer or "").strip()
    if not value:
        return [
            OutboundMessage(text="Нужен ответ на вопрос."),
            await _render_screening_prompt(session, candidate, journey),
        ]

    if question.get("options"):
        matched = _match_option(question, value)
        if matched is None:
            return [
                OutboundMessage(text="Выберите один из вариантов кнопкой ниже."),
                await _render_screening_prompt(session, candidate, journey),
            ]
        value = matched

    answers[qid] = value
    await save_screening_draft(session, journey, answers=answers)

    remaining = _screening_question(answers)
    if remaining is None:
        await complete_screening(
            session,
            candidate,
            journey,
            answers=answers,
            source_channel="max_bot",
        )
    return await _render_next_step(session, candidate, journey)


async def process_bot_started(
    *,
    max_user_id: str,
    display_name: str | None = None,
    start_payload: str | None = None,
) -> list[OutboundMessage]:
    async with async_session() as session:
        async with session.begin():
            candidate = await _ensure_max_candidate(
                session,
                max_user_id=max_user_id,
                display_name=display_name,
                start_payload=start_payload,
            )
            journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
            payload = await build_candidate_portal_journey(session, candidate, entry_channel="max")

            current_step = str(payload["journey"].get("current_step") or "")
            if current_step in {"profile", "screening"}:
                started = current_step == "screening" or bool((payload["journey"].get("profile") or {}).get("fio"))
                cta = "Продолжить анкету" if started else "Начать анкету"
                return [
                    OutboundMessage(
                        text=(
                            "Здравствуйте! Здесь можно пройти первичную анкету прямо в MAX.\n"
                            "После этого мы дадим ссылку на выбор времени собеседования."
                        ),
                        buttons=[[InlineButton(text=cta, callback_data=WELCOME_CALLBACK)]],
                    )
                ]

            return [await _render_status_message(session, candidate)]


async def process_start_or_resume(
    *,
    max_user_id: str,
) -> list[OutboundMessage]:
    async with async_session() as session:
        async with session.begin():
            candidate = await _ensure_max_candidate(session, max_user_id=max_user_id)
            journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
            return await _render_next_step(session, candidate, journey)


async def process_text_message(
    *,
    max_user_id: str,
    text: str,
    display_name: str | None = None,
    start_payload: str | None = None,
    raw_event: dict[str, Any] | None = None,
) -> list[OutboundMessage]:
    clean_text = str(text or "").strip()
    if not clean_text:
        return []

    async with async_session() as session:
        async with session.begin():
            candidate = await _ensure_max_candidate(
                session,
                max_user_id=max_user_id,
                display_name=display_name,
                start_payload=start_payload,
            )
            journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
            payload = await build_candidate_portal_journey(session, candidate, entry_channel="max")
            current_step = str(payload["journey"].get("current_step") or "")

            if clean_text.lower() in {"/start", "start", "начать", "resume", "продолжить"}:
                return await _render_next_step(session, candidate, journey)

            if current_step == "profile":
                return await _profile_answer(session, candidate=candidate, journey=journey, answer=clean_text)

            if current_step == "screening":
                return await _screening_answer(session, candidate=candidate, journey=journey, answer=clean_text)

            await _log_inbound_max_chat(
                session,
                candidate=candidate,
                text=clean_text,
                payload={"source": "max", "max_user_id": max_user_id, "event": raw_event or {}},
            )
            return [
                OutboundMessage(text="Сообщение передано рекрутеру."),
                await _render_status_message(session, candidate),
            ]


async def process_callback(
    *,
    max_user_id: str,
    payload: str,
) -> list[OutboundMessage]:
    if payload == WELCOME_CALLBACK:
        return await process_start_or_resume(max_user_id=max_user_id)

    if payload == PORTAL_CALLBACK:
        return await process_start_or_resume(max_user_id=max_user_id)

    if not payload.startswith(QUESTION_CALLBACK_PREFIX):
        return [OutboundMessage(text="Принято! Ваш запрос обрабатывается.")]

    raw = payload[len(QUESTION_CALLBACK_PREFIX):]
    question_id, _, option_idx_raw = raw.partition(":")
    try:
        option_idx = int(option_idx_raw)
    except ValueError:
        return [OutboundMessage(text="Кнопка устарела. Отправляю актуальный вопрос ещё раз.")]

    async with async_session() as session:
        async with session.begin():
            candidate = await _ensure_max_candidate(session, max_user_id=max_user_id)
            journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
            journey_payload = await build_candidate_portal_journey(session, candidate, entry_channel="max")
            if str(journey_payload["journey"].get("current_step") or "") != "screening":
                return await _render_next_step(session, candidate, journey)

            screening_state = next((item for item in journey.step_states if item.step_key == "screening"), None)
            answers = dict(screening_state.payload_json or {}) if screening_state and screening_state.payload_json else {}
            question = _screening_question(answers)
            if question is None:
                return await _render_next_step(session, candidate, journey)

            options = list(question.get("options") or [])
            if option_idx < 0 or option_idx >= len(options):
                return [
                    OutboundMessage(text="Кнопка устарела. Отправляю актуальный вопрос ещё раз."),
                    await _render_screening_prompt(session, candidate, journey),
                ]

            return await _screening_answer(
                session,
                candidate=candidate,
                journey=journey,
                answer=str(options[option_idx]),
                forced_question_id=question_id or None,
            )


def extract_message_text(event: dict[str, Any]) -> str:
    message = event.get("message", {})
    body = message.get("body", {})
    text = body.get("text")
    return str(text or "").strip()


def extract_message_user(event: dict[str, Any]) -> tuple[str | None, str | None]:
    message = event.get("message", {})
    sender = message.get("sender", {})
    user_id = sender.get("user_id") or sender.get("chat_id")
    user_name = sender.get("name") or sender.get("username")
    if user_id is None:
        user = event.get("user")
        if isinstance(user, dict):
            user_id = user.get("user_id")
            user_name = user_name or user.get("name") or user.get("username")
    return (str(user_id).strip() if user_id is not None else None), (str(user_name).strip() if user_name else None)


def extract_callback_user(event: dict[str, Any]) -> tuple[str | None, str | None]:
    callback = event.get("callback", {})
    user = callback.get("user", {}) if isinstance(callback, dict) else {}
    user_id = user.get("user_id") or callback.get("chat_id")
    user_name = user.get("name") or user.get("username")
    return (str(user_id).strip() if user_id is not None else None), (str(user_name).strip() if user_name else None)


__all__ = [
    "OutboundMessage",
    "PORTAL_CALLBACK",
    "QUESTION_CALLBACK_PREFIX",
    "WELCOME_CALLBACK",
    "extract_callback_user",
    "extract_message_text",
    "extract_message_user",
    "process_bot_started",
    "process_callback",
    "process_start_or_resume",
    "process_text_message",
    "send_outbound",
]
