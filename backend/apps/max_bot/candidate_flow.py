"""Candidate-facing MAX bot flow built on top of the universal journey layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import html
import logging
import re
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.apps.bot.city_registry import find_candidate_city_by_name, list_candidate_cities
from backend.apps.bot.test1_validation import apply_partial_validation
from backend.core.audit import log_audit_action
from backend.core.db import async_session
from backend.core.messenger.reliability import default_max_public_entry_enabled
from backend.core.settings import get_settings
import backend.core.messenger.registry as messenger_registry
from backend.core.messenger.protocol import InlineButton, MessengerPlatform
from backend.domain import analytics
from backend.domain.candidate_status_service import CandidateStatusService
from backend.domain.candidates.models import (
    CandidateChatRead,
    CandidateInviteToken,
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
    build_candidate_max_mini_app_url,
    build_candidate_portal_url,
    bump_candidate_portal_session_version,
    complete_screening,
    ensure_candidate_portal_session,
    get_candidate_portal_questions,
    save_candidate_profile,
    save_screening_draft,
    resolve_candidate_portal_access_token,
    resolve_candidate_portal_user,
    sign_candidate_portal_token,
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


@dataclass(frozen=True)
class CandidateResolution:
    candidate: User | None
    status: str
    payload_linked: bool = False
    candidate_created: bool = False
    audit_events: tuple["AuditEvent", ...] = ()


@dataclass(frozen=True)
class AuditEvent:
    action: str
    entity_id: int | None
    changes: dict[str, Any]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _max_numeric_id(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def _normalize_invite_channel(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"max", "vkmax", "vk_max"}:
        return "max"
    if normalized == "generic":
        return "generic"
    return "telegram"


def _candidate_has_telegram_identity(candidate: User) -> bool:
    return any(
        (
            candidate.telegram_id is not None,
            candidate.telegram_user_id is not None,
            bool((candidate.telegram_username or "").strip()),
            candidate.telegram_linked_at is not None,
        )
    )


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


def _portal_mini_app_url(
    candidate: User,
    *,
    journey_session_id: int,
    session_version: int,
) -> str:
    if not (candidate.candidate_id or candidate.telegram_id):
        return ""
    portal_token = sign_candidate_portal_token(
        candidate_uuid=str(candidate.candidate_id) if candidate.candidate_id else None,
        telegram_id=int(candidate.telegram_id) if candidate.telegram_id is not None and not candidate.candidate_id else None,
        entry_channel="max",
        source_channel="max_app",
        journey_session_id=journey_session_id,
        session_version=session_version,
    )
    return build_candidate_max_mini_app_url(start_param=portal_token)


def _portal_entry_urls(
    candidate: User,
    *,
    journey_session_id: int,
    session_version: int,
) -> tuple[str | None, str | None]:
    portal_url = build_candidate_portal_url(
        candidate_uuid=str(candidate.candidate_id) if candidate.candidate_id else None,
        telegram_id=int(candidate.telegram_id) if candidate.telegram_id is not None and not candidate.candidate_id else None,
        entry_channel="max",
        source_channel="max_bot",
        journey_session_id=journey_session_id,
        session_version=session_version,
    )
    mini_app_url = _portal_mini_app_url(
        candidate,
        journey_session_id=journey_session_id,
        session_version=session_version,
    )
    return portal_url, mini_app_url


def _portal_entry_buttons_from_urls(
    *,
    portal_url: str | None,
    mini_app_url: str | None,
) -> list[list[InlineButton]] | None:
    buttons: list[list[InlineButton]] = []
    if mini_app_url:
        buttons.append([InlineButton(text="Открыть кабинет", url=mini_app_url, kind="web_app")])
    if portal_url:
        buttons.append([InlineButton(text="Открыть в браузере", url=portal_url, kind="link")])
    return buttons or None


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


def _invite_required_message(status: str) -> OutboundMessage:
    if status == "invalid_invite":
        return OutboundMessage(
            text=(
                "Ссылка для входа в MAX недействительна или устарела.\n"
                "Попросите рекрутера отправить новую персональную ссылку."
            )
        )
    if status == "invite_conflict":
        return OutboundMessage(
            text=(
                "Эта ссылка уже привязана к другому аккаунту MAX.\n"
                "Попросите рекрутера выпустить новую персональную ссылку."
            )
        )
    return OutboundMessage(
        text=(
            "Чтобы продолжить в MAX, нужна персональная ссылка от рекрутера.\n"
            "Без неё бот не может открыть вашу анкету."
        )
        )


def _new_max_candidate(*, max_user_id: str, now: datetime) -> User:
    return User(
        fio=f"MAX {max_user_id}",
        last_activity=now,
        source="max_bot_public",
        messenger_platform=None,
        max_user_id=max_user_id,
        is_active=True,
    )


async def _resolve_max_candidate(
    session: AsyncSession,
    *,
    max_user_id: str,
    display_name: str | None = None,
    start_payload: str | None = None,
) -> CandidateResolution:
    now = _utcnow()
    audit_events: list[AuditEvent] = []
    existing_by_max = await session.scalar(
        select(User)
        .where(User.max_user_id == max_user_id)
        .order_by(User.id.asc())
        .limit(1)
    )
    raw_payload = str(start_payload or "").strip()

    candidate = existing_by_max
    payload_linked = False
    linked_now = False
    candidate_created = False

    if candidate is None:
        if raw_payload:
            try:
                access = await resolve_candidate_portal_access_token(session, raw_payload)
            except CandidatePortalError:
                access = None

            if access is not None:
                try:
                    candidate = await resolve_candidate_portal_user(session, access)
                except CandidatePortalError:
                    return CandidateResolution(candidate=None, status="invalid_invite")
                existing_link = await session.scalar(
                    select(User)
                    .where(User.max_user_id == max_user_id)
                    .where(User.id != candidate.id)
                    .limit(1)
                )
                if existing_link is not None:
                    audit_events.append(
                        AuditEvent(
                            action="invite_conflict",
                            entity_id=int(candidate.id),
                            changes={"channel": "max", "max_user_id": max_user_id, "reason": "existing_link"},
                        )
                    )
                    return CandidateResolution(
                        candidate=None,
                        status="invite_conflict",
                        audit_events=tuple(audit_events),
                    )

                if candidate.max_user_id and candidate.max_user_id != max_user_id:
                    audit_events.append(
                        AuditEvent(
                            action="max_relink_attempt",
                            entity_id=int(candidate.id),
                            changes={
                                "channel": "max",
                                "current_max_user_id": candidate.max_user_id,
                                "incoming_max_user_id": max_user_id,
                            },
                        )
                    )
                    return CandidateResolution(
                        candidate=None,
                        status="invite_conflict",
                        audit_events=tuple(audit_events),
                    )

                linked_now = candidate.max_user_id in {None, "", max_user_id}
                candidate.max_user_id = max_user_id
                payload_linked = True
            else:
                invite = await session.scalar(
                    select(CandidateInviteToken)
                    .where(CandidateInviteToken.token == raw_payload)
                    .limit(1)
                )
                if invite is None:
                    return CandidateResolution(candidate=None, status="invalid_invite")
                if _normalize_invite_channel(invite.channel) not in {"generic", "max"}:
                    return CandidateResolution(candidate=None, status="invalid_invite")
                if (invite.status or "active") not in {"active", "used"}:
                    return CandidateResolution(candidate=None, status="invalid_invite")

                settings = get_settings()
                invite_ttl = timedelta(seconds=settings.candidate_portal_token_ttl_seconds)
                created_at = invite.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if now - created_at > invite_ttl:
                    return CandidateResolution(candidate=None, status="invalid_invite")

                candidate = await session.scalar(
                    select(User).where(User.candidate_id == invite.candidate_id).limit(1)
                )
                if candidate is None:
                    return CandidateResolution(candidate=None, status="invalid_invite")

                existing_link = await session.scalar(
                    select(User)
                    .where(User.max_user_id == max_user_id)
                    .where(User.id != candidate.id)
                    .limit(1)
                )
                if existing_link is not None:
                    audit_events.append(
                        AuditEvent(
                            action="invite_conflict",
                            entity_id=int(candidate.id),
                            changes={"channel": "max", "max_user_id": max_user_id, "reason": "existing_link"},
                        )
                    )
                    return CandidateResolution(
                        candidate=None,
                        status="invite_conflict",
                        audit_events=tuple(audit_events),
                    )

                if candidate.max_user_id and candidate.max_user_id != max_user_id:
                    audit_events.append(
                        AuditEvent(
                            action="max_relink_attempt",
                            entity_id=int(candidate.id),
                            changes={
                                "channel": "max",
                                "current_max_user_id": candidate.max_user_id,
                                "incoming_max_user_id": max_user_id,
                            },
                        )
                    )
                    return CandidateResolution(
                        candidate=None,
                        status="invite_conflict",
                        audit_events=tuple(audit_events),
                    )

                if invite.used_at is not None and invite.used_by_external_id not in {None, "", max_user_id}:
                    audit_events.append(
                        AuditEvent(
                            action="invite_conflict",
                            entity_id=int(candidate.id),
                            changes={
                                "channel": "max",
                                "max_user_id": max_user_id,
                                "reason": "invite_already_used",
                            },
                        )
                    )
                    return CandidateResolution(
                        candidate=None,
                        status="invite_conflict",
                        audit_events=tuple(audit_events),
                    )

                linked_now = invite.used_at is None and candidate.max_user_id in {None, "", max_user_id}
                if invite.used_at is None:
                    invite.used_at = now
                invite.status = "used"
                invite.used_by_external_id = max_user_id
                candidate.max_user_id = max_user_id
                payload_linked = True
        else:
            allow_public_entry = bool(
                getattr(get_settings(), "max_bot_allow_public_entry", default_max_public_entry_enabled())
            )
            if not allow_public_entry:
                return CandidateResolution(candidate=None, status="invite_required")
            candidate = _new_max_candidate(max_user_id=max_user_id, now=now)
            session.add(candidate)
            await session.flush()
            linked_now = True
            candidate_created = True

    assert candidate is not None

    candidate.max_user_id = max_user_id
    current_platform = str(candidate.messenger_platform or "").strip().lower()
    if candidate_created or current_platform == "max" or (
        current_platform in {"", "telegram"} and not _candidate_has_telegram_identity(candidate)
    ):
        candidate.messenger_platform = "max"
    candidate.last_activity = now
    if not candidate.source:
        candidate.source = "max_bot"
    if candidate.candidate_status is None:
        await _status_service.force(candidate, CandidateStatus.LEAD, reason="max bot entry")

    if linked_now:
        audit_events.append(
            AuditEvent(
                action="max_linked",
                entity_id=int(candidate.id),
                changes={"channel": "max", "max_user_id": max_user_id, "payload_linked": payload_linked},
            )
        )
        await analytics.log_funnel_event(
            analytics.FunnelEvent.BOT_ENTERED,
            user_id=_max_numeric_id(max_user_id),
            candidate_id=candidate.id,
            metadata={"channel": "max", "max_user_id": max_user_id},
            session=session,
        )

    await analytics.log_funnel_event(
        analytics.FunnelEvent.BOT_START,
        user_id=_max_numeric_id(max_user_id),
        candidate_id=candidate.id,
        metadata={"channel": "max", "max_user_id": max_user_id},
        session=session,
    )
    if payload_linked:
        await bump_candidate_portal_session_version(session, candidate_id=int(candidate.id))

    await session.flush()
    logger.info("max_bot.candidate_resolved")
    return CandidateResolution(
        candidate=candidate,
        status="created" if candidate_created else ("linked" if payload_linked else "existing"),
        payload_linked=payload_linked,
        candidate_created=candidate_created,
        audit_events=tuple(audit_events),
    )


async def _emit_audit_events(events: tuple[AuditEvent, ...]) -> None:
    for event in events:
        await log_audit_action(
            event.action,
            "candidate",
            event.entity_id,
            changes=event.changes,
        )


async def _render_status_message(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
) -> OutboundMessage:
    payload = await build_candidate_portal_journey(session, candidate, entry_channel="max")
    portal_url = payload["candidate"].get("portal_url")
    company_summary = str(payload.get("company", {}).get("summary") or "").strip()
    next_action = payload["journey"].get("next_action") or "Следующий шаг уже сохранён в вашем профиле."
    status_label = payload["candidate"].get("status_label") or "В обработке"
    active_slot = payload["journey"]["slots"].get("active")
    mini_app_url = _portal_mini_app_url(
        candidate,
        journey_session_id=int(journey.id),
        session_version=int(journey.session_version or 1),
    )
    buttons = _portal_entry_buttons_from_urls(
        portal_url=portal_url,
        mini_app_url=mini_app_url,
    )

    lines = [
        f"Ваш статус: <b>{html.escape(str(status_label))}</b>",
        html.escape(str(next_action)),
    ]
    if company_summary:
        lines.append("")
        lines.append(html.escape(company_summary))
    if active_slot and active_slot.get("start_utc"):
        lines.append(f"Назначенный слот: <code>{html.escape(str(active_slot['start_utc']))}</code>")
    if mini_app_url:
        lines.append("")
        lines.append("Личный кабинет открыт в MAX.")
    elif portal_url:
        lines.append("")
        lines.append(f"Продолжить: {portal_url}")
    if portal_url and not buttons:
        lines.append("")
        lines.append(f"Продолжить: {portal_url}")

    return OutboundMessage(text="\n".join(lines), buttons=buttons)


async def _render_profile_prompt(
    session: AsyncSession,
    candidate: User,
    journey: CandidateJourneySession,
) -> OutboundMessage:
    profile_state = next((item for item in journey.step_states if item.step_key == "profile"), None)
    field = _next_profile_field(candidate, profile_state)
    if field is None:
        return await _render_status_message(session, candidate, journey)

    prompt = PROFILE_PROMPTS[field]
    if field == "city":
        cities = await list_candidate_cities()
        preview = ", ".join(city.display_name for city in cities[:8])
        if preview:
            prompt = f"{prompt}\n\nСейчас доступны города: <i>{html.escape(preview)}</i>"
    portal_url, mini_app_url = _portal_entry_urls(
        candidate,
        journey_session_id=int(journey.id),
        session_version=int(journey.session_version or 1),
    )
    return OutboundMessage(
        text=prompt,
        buttons=_portal_entry_buttons_from_urls(portal_url=portal_url, mini_app_url=mini_app_url),
    )


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
        return await _render_status_message(session, candidate, journey)

    await _ensure_screening_started(session, candidate=candidate, journey=journey)
    prompt = str(question.get("prompt") or "")
    helper = str(question.get("helper") or "").strip()
    question_index = int(question.get("index") or 0)
    total = len(get_candidate_portal_questions())
    title = f"Вопрос {question_index}/{total}" if question_index else "Следующий вопрос"
    text = f"<b>{title}</b>\n\n{prompt}"
    if helper:
        text += f"\n\n<i>{helper}</i>"
    buttons = _question_buttons(question)
    portal_url, mini_app_url = _portal_entry_urls(
        candidate,
        journey_session_id=int(journey.id),
        session_version=int(journey.session_version or 1),
    )
    portal_buttons = _portal_entry_buttons_from_urls(portal_url=portal_url, mini_app_url=mini_app_url)
    if buttons and portal_buttons:
        buttons = [*buttons, *portal_buttons]
    elif portal_buttons:
        buttons = portal_buttons
    return OutboundMessage(text=text, buttons=buttons)


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
            await _render_status_message(session, candidate, journey),
        ]
    return [await _render_status_message(session, candidate, journey)]


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
        logger.exception("max_bot.send_failed")
        raise


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
    audit_events: tuple[AuditEvent, ...] = ()
    messages: list[OutboundMessage]
    async with async_session() as session:
        async with session.begin():
            resolution = await _resolve_max_candidate(
                session,
                max_user_id=max_user_id,
                display_name=display_name,
                start_payload=start_payload,
            )
            audit_events = resolution.audit_events
            if resolution.candidate is None:
                messages = [_invite_required_message(resolution.status)]
            else:
                candidate = resolution.candidate
                journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
                next_messages = await _render_next_step(session, candidate, journey)
                intro = OutboundMessage(
                    text=(
                        "Здравствуйте! Здесь можно пройти первичную анкету прямо в MAX.\n"
                        "После этого мы дадим ссылку на выбор времени собеседования."
                    ),
                )
                if resolution.candidate_created or resolution.payload_linked:
                    messages = [intro, *next_messages]
                elif next_messages and "кабинете кандидата" not in str(next_messages[0].text).lower():
                    messages = [intro, *next_messages]
                else:
                    messages = next_messages
    await _emit_audit_events(audit_events)
    return messages


async def process_start_or_resume(
    *,
    max_user_id: str,
) -> list[OutboundMessage]:
    audit_events: tuple[AuditEvent, ...] = ()
    messages: list[OutboundMessage]
    async with async_session() as session:
        async with session.begin():
            resolution = await _resolve_max_candidate(session, max_user_id=max_user_id)
            audit_events = resolution.audit_events
            if resolution.candidate is None:
                messages = [_invite_required_message(resolution.status)]
            else:
                candidate = resolution.candidate
                journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
                messages = await _render_next_step(session, candidate, journey)
    await _emit_audit_events(audit_events)
    return messages


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

    audit_events: tuple[AuditEvent, ...] = ()
    messages: list[OutboundMessage]
    async with async_session() as session:
        async with session.begin():
            resolution = await _resolve_max_candidate(
                session,
                max_user_id=max_user_id,
                display_name=display_name,
                start_payload=start_payload,
            )
            audit_events = resolution.audit_events
            if resolution.candidate is None:
                messages = [_invite_required_message(resolution.status)]
            else:
                candidate = resolution.candidate
                journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
                payload = await build_candidate_portal_journey(session, candidate, entry_channel="max")
                current_step = str(payload["journey"].get("current_step") or "")

                if clean_text.lower() in {"/start", "start", "начать", "resume", "продолжить"}:
                    messages = await _render_next_step(session, candidate, journey)
                elif current_step == "profile":
                    messages = await _profile_answer(
                        session,
                        candidate=candidate,
                        journey=journey,
                        answer=clean_text,
                    )
                elif current_step == "screening":
                    messages = await _screening_answer(
                        session,
                        candidate=candidate,
                        journey=journey,
                        answer=clean_text,
                    )
                else:
                    await _log_inbound_max_chat(
                        session,
                        candidate=candidate,
                        text=clean_text,
                        payload={"source": "max", "max_user_id": max_user_id, "event": raw_event or {}},
                    )
                    messages = [
                        OutboundMessage(text="Сообщение передано рекрутеру."),
                        await _render_status_message(session, candidate, journey),
                    ]
    await _emit_audit_events(audit_events)
    return messages


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

    audit_events: tuple[AuditEvent, ...] = ()
    messages: list[OutboundMessage]
    async with async_session() as session:
        async with session.begin():
            resolution = await _resolve_max_candidate(session, max_user_id=max_user_id)
            audit_events = resolution.audit_events
            if resolution.candidate is None:
                messages = [_invite_required_message(resolution.status)]
            else:
                candidate = resolution.candidate
                journey = await ensure_candidate_portal_session(session, candidate, entry_channel="max")
                journey_payload = await build_candidate_portal_journey(session, candidate, entry_channel="max")
                if str(journey_payload["journey"].get("current_step") or "") != "screening":
                    messages = await _render_next_step(session, candidate, journey)
                else:
                    screening_state = next(
                        (item for item in journey.step_states if item.step_key == "screening"),
                        None,
                    )
                    answers = (
                        dict(screening_state.payload_json or {})
                        if screening_state and screening_state.payload_json
                        else {}
                    )
                    question = _screening_question(answers)
                    if question is None:
                        messages = await _render_next_step(session, candidate, journey)
                    else:
                        options = list(question.get("options") or [])
                        if option_idx < 0 or option_idx >= len(options):
                            messages = [
                                OutboundMessage(text="Кнопка устарела. Отправляю актуальный вопрос ещё раз."),
                                await _render_screening_prompt(session, candidate, journey),
                            ]
                        else:
                            messages = await _screening_answer(
                                session,
                                candidate=candidate,
                                journey=journey,
                                answer=str(options[option_idx]),
                                forced_question_id=question_id or None,
                            )
    await _emit_audit_events(audit_events)
    return messages


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
