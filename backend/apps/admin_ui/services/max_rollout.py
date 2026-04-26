from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.apps.admin_ui.security import Principal
from backend.core.audit import log_audit_action
from backend.core.db import async_session
from backend.core.messenger.bootstrap import ensure_max_adapter
from backend.core.messenger.max_recovery import (
    compute_max_delivery_next_retry_at,
    mark_max_message_retryable_failure,
    serialize_inline_buttons,
)
from backend.core.messenger.protocol import InlineButton
from backend.core.settings import Settings, get_settings
from backend.domain.applications import (
    ApplicationEventCommand,
    ApplicationEventPublisher,
    ApplicationEventType,
    SqlAlchemyApplicationEventRepository,
    SqlAlchemyApplicationUnitOfWork,
)
from backend.domain.candidates.max_launch_invites import (
    MaxLaunchInviteError,
    MaxLaunchInviteLifecycleAction,
    create_max_launch_invite,
)
from backend.domain.candidates.models import (
    CandidateAccessSession,
    CandidateAccessSessionStatus,
    CandidateAccessToken,
    CandidateAccessTokenKind,
    CandidateJourneyEvent,
    CandidateJourneySession,
    CandidateJourneyStepState,
    CandidateJourneySurface,
    CandidateLaunchChannel,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    User,
)
from backend.domain.candidates.test1_shared import TEST1_STEP_KEY
from backend.domain.idempotency import (
    has_max_provider_boundary,
    max_provider_message_id,
    max_rollout_invite_send_key,
)
from backend.domain.models import Slot, SlotStatus


class MaxInviteRolloutDisabledError(RuntimeError):
    pass


@dataclass(frozen=True)
class MaxInviteIssueRequest:
    candidate_id: int
    application_id: int | None
    dry_run: bool
    send: bool
    reuse_policy: str
    principal: Principal


VALID_REUSE_POLICIES = {"reuse_active", "rotate_active"}

MAX_ROLLOUT_STATUS_LABELS = {
    "disabled": "Пилот MAX выключен",
    "not_issued": "Не выдавалось",
    "issued": "Выдано",
    "sent": "Отправлено",
    "send_failed": "Ошибка отправки",
    "revoked": "Отозвано",
    "expired": "Истекло",
    "launched": "Запущено",
    "active": "Активно",
    "preview_ready": "Готово к предпросмотру",
}

SCREENING_STATUS_LABELS = {
    "pending": "Ожидает решения",
    "advance": "Рекомендуем двигать дальше",
    "recommended": "Рекомендуем двигать дальше",
    "pass": "Рекомендуем двигать дальше",
    "passed": "Рекомендуем двигать дальше",
    "manual_review": "Нужна ручная проверка",
    "review": "Нужна ручная проверка",
    "reject": "Не рекомендован",
    "rejected": "Не рекомендован",
    "declined": "Не рекомендован",
    "not_recommended": "Не рекомендован",
}

BOOKING_STATUS_LABELS = {
    SlotStatus.PENDING: "Ожидает подтверждения",
    SlotStatus.BOOKED: "Запись создана",
    SlotStatus.CONFIRMED: "Подтверждено",
    SlotStatus.CONFIRMED_BY_CANDIDATE: "Подтверждено кандидатом",
    SlotStatus.CANCELED: "Отменено",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        value = datetime.fromisoformat(normalized)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_compact_dt(value: datetime | None) -> str | None:
    normalized = _as_utc(value)
    if normalized is None:
        return None
    return normalized.strftime("%d.%m.%Y %H:%M UTC")


def _format_rollout_status_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "Не задано"
    return MAX_ROLLOUT_STATUS_LABELS.get(
        normalized,
        normalized.replace("_", " "),
    )


def _format_screening_status_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return SCREENING_STATUS_LABELS["pending"]
    return SCREENING_STATUS_LABELS.get(
        normalized,
        normalized.replace("_", " "),
    )


def _format_booking_status_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "Активной записи пока нет"
    return BOOKING_STATUS_LABELS.get(
        normalized,
        normalized.replace("_", " "),
    )


def _rollout_summary_copy(*, enabled: bool, status: str) -> tuple[str, str]:
    normalized = str(status or "").strip().lower()
    if not enabled and normalized == "disabled":
        return (
            "Пилот MAX выключен по умолчанию и доступен только в контролируемом запуске.",
            "Включайте MAX только для согласованного пилотного контура.",
        )
    if normalized == "not_issued":
        return (
            "Приглашение в MAX ещё не выдавалось.",
            "Сначала откройте предпросмотр, затем отправьте приглашение кандидату.",
        )
    if normalized == "issued":
        return (
            "Приглашение подготовлено и готово к отправке кандидату.",
            "Проверьте предпросмотр перед отправкой.",
        )
    if normalized == "sent":
        return (
            "Приглашение отправлено кандидату в MAX.",
            "Проверьте, открыл ли кандидат mini app и как двигается по шагам ниже.",
        )
    if normalized == "launched":
        return (
            "Кандидат уже открыл MAX mini app.",
            "Проверьте прогресс кандидата и текущий следующий шаг.",
        )
    if normalized == "revoked":
        return (
            "Приглашение в MAX отозвано.",
            "При необходимости перевыпустите приглашение перед повторной отправкой.",
        )
    if normalized == "expired":
        return (
            "Срок действия приглашения истёк.",
            "Перевыпустите приглашение перед повторной отправкой.",
        )
    if normalized == "send_failed":
        return (
            "Отправка в MAX не завершилась.",
            "Проверьте предпросмотр и повторите отправку в рамках пилота.",
        )
    return (
        "MAX mini app доступен в контролируемом пилотном контуре.",
        "Используйте этот блок только для ограниченных операторских действий.",
    )


def _build_rollout_snapshot(
    *,
    enabled: bool,
    token: CandidateAccessToken | None,
    access_session: CandidateAccessSession | None,
    now: datetime,
) -> dict[str, Any]:
    if token is None:
        return {
            "enabled": enabled,
            "invite_state": "not_issued",
            "send_state": "not_sent",
            "launch_state": "not_launched",
            "launched_at": None,
        }

    observation = _launch_observation(token=token, access_session=access_session, now=now)
    invite_state = _invite_state(token=token, access_session=access_session, now=now)
    send_state = str((token.launch_payload_json or {}).get("send_state") or "not_sent")
    return {
        "enabled": enabled,
        "invite_state": invite_state,
        "send_state": send_state,
        "launch_state": "launched" if observation["launched"] else "not_launched",
        "launched_at": observation["launched_at"],
    }


def _rollout_enabled(settings: Settings) -> bool:
    return bool(getattr(settings, "max_invite_rollout_enabled", False))


def _redact_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    parsed = urlsplit(normalized)
    query = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in {"startapp", "start"} and item:
            query.append((key, "***"))
        else:
            query.append((key, item))
    return urlunsplit(parsed._replace(query=urlencode(query)))


def _launch_observation(
    *,
    token: CandidateAccessToken,
    access_session: CandidateAccessSession | None,
    now: datetime,
) -> dict[str, Any]:
    access_session_expires = _as_utc(
        access_session.expires_at if access_session is not None else None
    )
    access_session_active = (
        access_session is not None
        and access_session.status == CandidateAccessSessionStatus.ACTIVE.value
        and access_session.revoked_at is None
        and access_session_expires is not None
        and access_session_expires > now
    )
    launched = bool(
        access_session_active
        or token.consumed_at is not None
        or token.last_seen_at is not None
    )
    return {
        "launched": launched,
        "launched_at": (
            _as_utc(access_session.issued_at if access_session is not None else token.consumed_at)
            if launched
            else None
        ),
        "access_session_id": access_session.id if access_session is not None else None,
        "provider_bound": bool(
            str(token.provider_user_id or "").strip()
            or (
                access_session is not None
                and str(access_session.provider_user_id or "").strip()
            )
        ),
    }


def _invite_state(
    *,
    token: CandidateAccessToken,
    access_session: CandidateAccessSession | None,
    now: datetime,
) -> str:
    if token.revoked_at is not None:
        return "revoked"
    expires_at = _as_utc(token.expires_at)
    if expires_at is not None and expires_at <= now:
        return "expired"
    if _launch_observation(token=token, access_session=access_session, now=now)["launched"]:
        return "launched"
    return "active"


async def _load_latest_launch_token(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int | None = None,
) -> CandidateAccessToken | None:
    stmt = (
        select(CandidateAccessToken)
        .where(
            CandidateAccessToken.candidate_id == candidate_id,
            CandidateAccessToken.token_kind == CandidateAccessTokenKind.LAUNCH.value,
            CandidateAccessToken.journey_surface == CandidateJourneySurface.MAX_MINIAPP.value,
            CandidateAccessToken.launch_channel == CandidateLaunchChannel.MAX.value,
            CandidateAccessToken.application_id.is_(application_id)
            if application_id is None
            else CandidateAccessToken.application_id == application_id,
        )
        .order_by(CandidateAccessToken.created_at.desc(), CandidateAccessToken.id.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_launch_access_session(
    session: AsyncSession,
    *,
    token_id: int,
) -> CandidateAccessSession | None:
    result = await session.execute(
        select(CandidateAccessSession)
        .where(CandidateAccessSession.origin_token_id == token_id)
        .order_by(CandidateAccessSession.issued_at.desc(), CandidateAccessSession.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _action_payload(key: str, label: str, kind: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "method": "POST",
        "kind": kind,
    }


def _audit_action_suffix(action: MaxLaunchInviteLifecycleAction) -> str:
    mapping = {
        MaxLaunchInviteLifecycleAction.ISSUED: "issue",
        MaxLaunchInviteLifecycleAction.REUSED: "reuse",
        MaxLaunchInviteLifecycleAction.ROTATED: "rotate",
        MaxLaunchInviteLifecycleAction.REVOKED: "revoke",
    }
    return mapping.get(action, action.value)


def _safe_launch_payload_snapshot(
    *,
    existing: dict[str, Any] | None,
    message_preview: str,
    send_state: str,
    launch_url: str | None,
    chat_url: str | None,
) -> dict[str, Any]:
    return {
        **dict(existing or {}),
        "launch_url_redacted": _redact_url(launch_url),
        "chat_url_redacted": _redact_url(chat_url),
        "message_preview": message_preview,
        "send_state": send_state,
    }


async def _load_candidate_flow_statuses(
    session: AsyncSession,
    *,
    candidate_id: int,
) -> list[dict[str, Any]]:
    candidate = await session.get(User, candidate_id)
    if candidate is None:
        return []

    step_state = await session.scalar(
        select(CandidateJourneyStepState)
        .join(
            CandidateJourneySession,
            CandidateJourneySession.id == CandidateJourneyStepState.session_id,
        )
        .where(CandidateJourneyStepState.step_key == TEST1_STEP_KEY)
        .where(CandidateJourneySession.candidate_id == candidate_id)
        .order_by(CandidateJourneyStepState.updated_at.desc(), CandidateJourneyStepState.id.desc())
        .limit(1)
    )
    completion = dict((step_state.payload_json or {}).get("completion") or {}) if step_state is not None else {}
    screening = dict(completion.get("screening_decision") or {})

    booking = await session.scalar(
        select(Slot)
        .where(
            Slot.candidate_id == candidate.candidate_id,
            Slot.status.in_(
                [
                    SlotStatus.PENDING,
                    SlotStatus.BOOKED,
                    SlotStatus.CONFIRMED,
                    SlotStatus.CONFIRMED_BY_CANDIDATE,
                ]
            ),
        )
        .order_by(Slot.start_utc.asc(), Slot.id.asc())
        .limit(1)
    )

    manual_review_event = await session.scalar(
        select(CandidateJourneyEvent)
        .where(
            CandidateJourneyEvent.candidate_id == candidate_id,
            CandidateJourneyEvent.event_key == "max_global_link_manual_review_required",
        )
        .order_by(CandidateJourneyEvent.created_at.desc(), CandidateJourneyEvent.id.desc())
        .limit(1)
    )

    return [
        {
            "key": "test1",
            "label": "Тест 1",
            "status": "completed" if completion.get("completed") else "pending",
            "status_label": "Завершён" if completion.get("completed") else "Не завершён",
            "detail": screening.get("explanation") if screening else "Кандидат ещё не завершил анкету.",
        },
        {
            "key": "screening",
            "label": "Скрининг",
            "status": str(screening.get("outcome") or "pending"),
            "status_label": _format_screening_status_label(screening.get("outcome")),
            "detail": screening.get("explanation") or "Решение ещё не зафиксировано.",
        },
        {
            "key": "booking",
            "label": "Собеседование",
            "status": str(getattr(booking, "status", "") or "pending"),
            "status_label": _format_booking_status_label(getattr(booking, "status", None)),
            "detail": (
                f"Назначено на {_format_compact_dt(getattr(booking, 'start_utc', None))}"
                if getattr(booking, "start_utc", None) is not None
                else "Активной записи пока нет."
            ),
        },
        {
            "key": "manual_review",
            "label": "Ручная проверка",
            "status": "required" if manual_review_event is not None else "clear",
            "status_label": "Нужна" if manual_review_event is not None else "Не нужна",
            "detail": manual_review_event.summary if manual_review_event is not None else "Вход по общей ссылке прошёл без ручного вмешательства.",
        },
    ]


async def build_candidate_max_rollout_summary(
    candidate_id: int,
    *,
    application_id: int | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    enabled = _rollout_enabled(resolved_settings)
    now = _utcnow()

    async with async_session() as session:
        token = await _load_latest_launch_token(
            session,
            candidate_id=candidate_id,
            application_id=application_id,
        )
        if token is None:
            summary_text, hint_text = _rollout_summary_copy(enabled=enabled, status="disabled" if not enabled else "not_issued")
            return {
                "enabled": enabled,
                "status": "disabled" if not enabled else "not_issued",
                "status_label": _format_rollout_status_label("disabled" if not enabled else "not_issued"),
                "summary": summary_text,
                "hint": hint_text,
                "preview_action_key": "preview",
                "send_action_key": "send",
                "reissue_action_key": "reissue",
                "revoke_action_key": "revoke",
                "actions": {
                    "preview": _action_payload("preview", "Предпросмотр", "preview"),
                    "send": _action_payload("send", "Отправить", "send"),
                    "reissue": _action_payload("reissue", "Перевыпустить", "reissue"),
                },
                "flow_statuses": await _load_candidate_flow_statuses(session, candidate_id=candidate_id),
            }

        access_session = await _load_launch_access_session(session, token_id=int(token.id))
        observation = _launch_observation(token=token, access_session=access_session, now=now)
        invite_state = _invite_state(token=token, access_session=access_session, now=now)
        send_state = str((token.launch_payload_json or {}).get("send_state") or "not_sent")
        status = (
            invite_state
            if invite_state != "active"
            else "send_failed"
            if send_state == "failed"
            else "sent"
            if send_state == "sent"
            else "issued"
        )
        summary_text, hint_text = _rollout_summary_copy(enabled=enabled, status=status)
        summary = {
            "enabled": enabled,
            "status": status,
            "status_label": _format_rollout_status_label(status),
            "summary": summary_text,
            "hint": hint_text,
            "issued_at": _as_utc(token.created_at),
            "sent_at": _as_utc((token.launch_payload_json or {}).get("last_sent_at")),
            "expires_at": _as_utc(token.expires_at),
            "revoked_at": _as_utc(token.revoked_at),
            "dry_run": bool((token.launch_payload_json or {}).get("send_state") == "preview_only"),
            "message_preview": (token.launch_payload_json or {}).get("message_preview"),
            "max_launch_url": str(
                (token.launch_payload_json or {}).get("launch_url_redacted") or ""
            )
            or None,
            "max_chat_url": str(
                (token.launch_payload_json or {}).get("chat_url_redacted") or ""
            )
            or None,
            "invite_state": invite_state,
            "send_state": send_state,
            "launch_state": "launched" if observation["launched"] else "not_launched",
            "launch_observation": observation,
            "access_token_id": int(token.id),
            "correlation_id": str(token.correlation_id or ""),
            "application_id": token.application_id,
            "preview_action_key": "preview",
            "send_action_key": "send",
            "reissue_action_key": "reissue",
            "revoke_action_key": "revoke",
            "actions": {
                "preview": _action_payload("preview", "Предпросмотр", "preview"),
                "send": _action_payload("send", "Отправить", "send"),
                "reissue": _action_payload("reissue", "Перевыпустить", "reissue"),
                "revoke": _action_payload("revoke", "Отозвать", "revoke"),
            },
            "flow_statuses": await _load_candidate_flow_statuses(session, candidate_id=candidate_id),
        }
        return summary


async def get_candidate_max_rollout_snapshots(
    candidate_ids: list[int] | tuple[int, ...],
    *,
    settings: Settings | None = None,
) -> dict[int, dict[str, Any]]:
    resolved_settings = settings or get_settings()
    enabled = _rollout_enabled(resolved_settings)
    normalized_ids = sorted({int(candidate_id) for candidate_id in candidate_ids if int(candidate_id) > 0})
    if not normalized_ids:
        return {}

    now = _utcnow()
    async with async_session() as session:
        latest_token_ids = (
            select(
                CandidateAccessToken.candidate_id.label("candidate_id"),
                func.max(CandidateAccessToken.id).label("token_id"),
            )
            .where(
                CandidateAccessToken.candidate_id.in_(normalized_ids),
                CandidateAccessToken.token_kind == CandidateAccessTokenKind.LAUNCH.value,
                CandidateAccessToken.journey_surface == CandidateJourneySurface.MAX_MINIAPP.value,
                CandidateAccessToken.launch_channel == CandidateLaunchChannel.MAX.value,
            )
            .group_by(CandidateAccessToken.candidate_id)
            .subquery()
        )
        token_rows = await session.execute(
            select(CandidateAccessToken)
            .join(latest_token_ids, CandidateAccessToken.id == latest_token_ids.c.token_id)
        )
        tokens = list(token_rows.scalars().all())
        tokens_by_candidate = {int(token.candidate_id): token for token in tokens}

        access_sessions_by_token_id: dict[int, CandidateAccessSession] = {}
        if tokens:
            latest_access_session_ids = (
                select(
                    CandidateAccessSession.origin_token_id.label("token_id"),
                    func.max(CandidateAccessSession.id).label("access_session_id"),
                )
                .where(
                    CandidateAccessSession.origin_token_id.in_([int(token.id) for token in tokens])
                )
                .group_by(CandidateAccessSession.origin_token_id)
                .subquery()
            )
            access_session_rows = await session.execute(
                select(CandidateAccessSession)
                .join(
                    latest_access_session_ids,
                    CandidateAccessSession.id == latest_access_session_ids.c.access_session_id,
                )
            )
            access_sessions_by_token_id = {
                int(access_session.origin_token_id): access_session
                for access_session in access_session_rows.scalars().all()
                if access_session.origin_token_id is not None
            }

    snapshots: dict[int, dict[str, Any]] = {}
    for candidate_id in normalized_ids:
        token = tokens_by_candidate.get(candidate_id)
        access_session = (
            access_sessions_by_token_id.get(int(token.id))
            if token is not None
            else None
        )
        snapshots[candidate_id] = _build_rollout_snapshot(
            enabled=enabled,
            token=token,
            access_session=access_session,
            now=now,
        )
    return snapshots


def _publish_event_sync(sync_session: Session, command: ApplicationEventCommand) -> None:
    uow = SqlAlchemyApplicationUnitOfWork(sync_session)
    publisher = ApplicationEventPublisher(
        SqlAlchemyApplicationEventRepository(sync_session, uow=uow)
    )
    with uow.begin():
        publisher.publish_application_event(command)


async def _publish_event(session: AsyncSession, command: ApplicationEventCommand) -> None:
    await session.run_sync(_publish_event_sync, command)


def _invite_event_request_mode(request: MaxInviteIssueRequest) -> str:
    if request.dry_run:
        return "preview"
    if request.send:
        return "send_request"
    return "issue"


async def _revoke_related_access_sessions(
    session: AsyncSession,
    *,
    token_ids: tuple[int, ...],
    now: datetime,
) -> None:
    if not token_ids:
        return
    result = await session.execute(
        select(CandidateAccessSession)
        .where(CandidateAccessSession.origin_token_id.in_(token_ids))
        .with_for_update()
    )
    for access_session in result.scalars().all():
        access_session.status = CandidateAccessSessionStatus.REVOKED.value
        access_session.revoked_at = now
        access_session.refreshed_at = now
        access_session.expires_at = now


async def _load_candidate_required(session: AsyncSession, candidate_id: int) -> User:
    candidate = await session.get(User, candidate_id)
    if candidate is None or not candidate.is_active:
        raise MaxLaunchInviteError("Candidate is unavailable for MAX rollout.")
    return candidate


async def _create_send_intent(
    session: AsyncSession,
    *,
    candidate: User,
    text: str,
    correlation_id: str,
    access_token_id: int,
    buttons: list[list[InlineButton]] | None = None,
) -> tuple[ChatMessage, bool]:
    now = _utcnow()
    client_request_id = max_rollout_invite_send_key(access_token_id)
    existing = await session.scalar(
        select(ChatMessage).where(ChatMessage.client_request_id == client_request_id)
    )
    if existing is not None:
        return existing, False

    message = ChatMessage(
        candidate_id=int(candidate.id),
        direction=ChatMessageDirection.OUTBOUND.value,
        channel="max",
        text=text,
        payload_json={
            "origin_channel": "crm",
            "delivery_channels": ["web", "max"],
            "author_role": "recruiter",
            "correlation_id": correlation_id,
            "launch_invite_token_id": access_token_id,
            "buttons": serialize_inline_buttons(buttons),
        },
        status=ChatMessageStatus.QUEUED.value,
        author_label="MAX pilot invite",
        client_request_id=client_request_id,
        delivery_attempts=0,
        delivery_locked_at=now,
        delivery_next_retry_at=None,
        delivery_last_attempt_at=None,
        delivery_dead_at=None,
    )
    session.add(message)
    await session.flush()
    return message, True


async def _persist_send_attempt_state(
    *,
    token_id: int,
    launch_url: str | None,
    chat_url: str | None,
    text: str,
    send_state: str,
    last_error_code: str | None = None,
) -> None:
    async with async_session() as session:
        async with session.begin():
            token = await session.get(CandidateAccessToken, token_id)
            if token is None:
                return
            token.launch_payload_json = {
                **_safe_launch_payload_snapshot(
                    existing=token.launch_payload_json,
                    launch_url=launch_url,
                    chat_url=chat_url,
                    message_preview=text,
                    send_state=send_state,
                ),
                "last_sent_at": _utcnow().isoformat(),
            }
            if last_error_code:
                token.launch_payload_json["last_error_code"] = last_error_code


async def issue_candidate_max_launch_invite(
    request: MaxInviteIssueRequest,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    if not _rollout_enabled(resolved_settings):
        raise MaxInviteRolloutDisabledError("MAX rollout surface is disabled.")
    if request.reuse_policy not in VALID_REUSE_POLICIES:
        raise MaxLaunchInviteError("Unsupported MAX invite reuse policy.")

    now = _utcnow()
    async with async_session() as session:
        async with session.begin():
            preview = await create_max_launch_invite(
                request.candidate_id,
                request.application_id,
                session=session,
                issued_by_type=request.principal.type,
                issued_by_id=str(request.principal.id),
                rotate_active=request.reuse_policy == "rotate_active",
                revoke_active=False,
            )
            active_token_id = int(preview.lifecycle.active_token_id or 0)
            token = await session.get(CandidateAccessToken, active_token_id)
            if token is None:
                raise MaxLaunchInviteError("MAX launch invite token was not created.")
            existing_payload = dict(token.launch_payload_json or {})
            existing_send_state = str(existing_payload.get("send_state") or "").strip()
            token.launch_payload_json = _safe_launch_payload_snapshot(
                existing=existing_payload,
                launch_url=preview.max_launch_url,
                chat_url=preview.max_chat_url,
                message_preview=preview.message_preview,
                send_state=(
                    "preview_only"
                    if request.dry_run
                    else existing_send_state or "not_sent"
                ),
            )
            await _publish_event(
                session,
                ApplicationEventCommand(
                    producer_family="max_candidate_access",
                    idempotency_key=(
                        f"{preview.lifecycle.action.value}:{token.token_id}:"
                        f"{_invite_event_request_mode(request)}"
                    ),
                    event_type=preview.lifecycle.event_type,
                    candidate_id=int(token.candidate_id),
                    application_id=token.application_id,
                    source_system="admin_ui",
                    source_ref=f"candidate:{request.candidate_id}:max_invite:{token.id}",
                    correlation_id=str(token.correlation_id or ""),
                    occurred_at=now,
                    actor_type=request.principal.type,
                    actor_id=request.principal.id,
                    channel=CandidateLaunchChannel.MAX.value,
                    metadata_json={
                        "token_id": int(token.id),
                        "journey_surface": token.journey_surface,
                        "auth_method": token.auth_method,
                        "launch_channel": token.launch_channel,
                        "reused_existing": preview.lifecycle.action
                        == MaxLaunchInviteLifecycleAction.REUSED,
                        "replaced_token_id": preview.lifecycle.replaced_token_id,
                        "revoked_token_ids": list(preview.lifecycle.revoked_token_ids),
                        "dry_run": request.dry_run,
                        "expires_at": _as_utc(token.expires_at).isoformat()
                        if _as_utc(token.expires_at) is not None
                        else None,
                    },
                ),
            )
            if preview.lifecycle.revoked_token_ids:
                await _revoke_related_access_sessions(
                    session,
                    token_ids=preview.lifecycle.revoked_token_ids,
                    now=now,
                )
            candidate = await _load_candidate_required(session, request.candidate_id)
            summary = await build_candidate_max_rollout_summary(
                request.candidate_id,
                application_id=request.application_id,
                settings=resolved_settings,
            )

        await log_audit_action(
            f"max_invite_{_audit_action_suffix(preview.lifecycle.action)}",
            "candidate",
            request.candidate_id,
            changes={
                "application_id": request.application_id,
                "token_id": active_token_id,
                "correlation_id": str(token.correlation_id or ""),
                "dry_run": request.dry_run,
                "send_requested": request.send,
                "reuse_policy": request.reuse_policy,
            },
        )

        send_state = "preview_only" if request.dry_run else str(summary.get("send_state") or "not_sent")
        status = "preview_ready" if request.dry_run else "issued"
        if request.send and not request.dry_run:
            should_send = not (
                preview.lifecycle.action == MaxLaunchInviteLifecycleAction.REUSED
                and send_state == "sent"
            )
            if should_send:
                send_result = await _send_candidate_max_launch_invite(
                    candidate=candidate,
                    token_id=active_token_id,
                    correlation_id=str(token.correlation_id or ""),
                    text=preview.message_preview,
                    launch_url=preview.max_launch_url,
                    chat_url=preview.max_chat_url,
                    settings=resolved_settings,
                )
                send_state = str(send_result["send_state"])
                status = "sent" if send_state == "sent" else "send_failed"
                summary = await build_candidate_max_rollout_summary(
                    request.candidate_id,
                    application_id=request.application_id,
                    settings=resolved_settings,
                )
                send_state = str(summary.get("send_state") or send_state)
            else:
                status = "sent"
                send_state = str(summary.get("send_state") or send_state)

        response = {
            "status": status,
            "dry_run": request.dry_run,
            "send_requested": request.send,
            "reused_existing": preview.lifecycle.action == MaxLaunchInviteLifecycleAction.REUSED,
            "invite_state": summary.get("invite_state") or "active",
            "send_state": send_state,
            "launch_state": summary.get("launch_state") or "not_launched",
            "message_preview": preview.message_preview,
            "expires_at": preview.expires_at,
            "access_token_id": active_token_id,
            "correlation_id": str(token.correlation_id or ""),
            "application_id": token.application_id,
            "launch_observation": summary.get("launch_observation"),
            "launch_artifact": {
                "launch_url": preview.max_launch_url if request.dry_run else None,
                "launch_url_redacted": None if request.dry_run else _redact_url(preview.max_launch_url),
                "chat_url_redacted": _redact_url(preview.max_chat_url),
            },
        }
        return response


async def _send_candidate_max_launch_invite(
    *,
    candidate: User,
    token_id: int,
    correlation_id: str,
    text: str,
    launch_url: str | None,
    chat_url: str | None,
    settings: Settings,
) -> dict[str, Any]:
    if not bool(getattr(settings, "max_adapter_enabled", False)):
        await _persist_send_attempt_state(
            token_id=token_id,
            launch_url=launch_url,
            chat_url=chat_url,
            text=text,
            send_state="preview_only",
            last_error_code="adapter_disabled",
        )
        return {"send_state": "preview_only", "status": "adapter_disabled"}
    if not str(getattr(settings, "max_bot_token", "") or "").strip():
        await _persist_send_attempt_state(
            token_id=token_id,
            launch_url=launch_url,
            chat_url=chat_url,
            text=text,
            send_state="failed",
            last_error_code="bot_token_missing",
        )
        return {"send_state": "failed", "status": "bot_token_missing"}
    max_user_id = str(getattr(candidate, "max_user_id", "") or "").strip()
    if not max_user_id:
        await _persist_send_attempt_state(
            token_id=token_id,
            launch_url=launch_url,
            chat_url=chat_url,
            text=text,
            send_state="preview_only",
            last_error_code="candidate_not_bound",
        )
        return {"send_state": "preview_only", "status": "candidate_not_bound"}

    now = _utcnow()
    buttons: list[list[InlineButton]] = []
    if launch_url:
        buttons.append(
            [InlineButton(text="Открыть MAX mini-app", url=launch_url, kind="open_app")]
        )
    elif chat_url:
        buttons.append([InlineButton(text="Открыть MAX", url=chat_url, kind="link")])

    async with async_session() as session:
        async with session.begin():
            db_candidate = await _load_candidate_required(session, int(candidate.id))
            message, created = await _create_send_intent(
                session,
                candidate=db_candidate,
                text=text,
                correlation_id=correlation_id,
                access_token_id=token_id,
                buttons=buttons or None,
            )
            if created:
                await _publish_event(
                    session,
                    ApplicationEventCommand(
                        producer_family="max_invite_delivery",
                        idempotency_key=f"message-intent:{message.client_request_id}",
                        event_type=ApplicationEventType.MESSAGE_INTENT_CREATED.value,
                        candidate_id=int(db_candidate.id),
                        source_system="admin_ui",
                        source_ref=f"chat_message:{message.id}",
                        correlation_id=correlation_id,
                        occurred_at=now,
                        actor_type="admin",
                        actor_id=0,
                        channel=CandidateLaunchChannel.MAX.value,
                        metadata_json={
                            "chat_message_id": int(message.id),
                            "token_id": token_id,
                        },
                    ),
                )
            queued_message_id = int(message.id)
            existing_status = str(message.status or "").strip().lower()
            existing_payload = dict(message.payload_json or {})

    if not created:
        if has_max_provider_boundary(status=existing_status, payload_json=existing_payload):
            await _persist_send_attempt_state(
                token_id=token_id,
                launch_url=launch_url,
                chat_url=chat_url,
                text=text,
                send_state="sent",
                last_error_code=None,
            )
            return {
                "send_state": "sent",
                "status": "sent",
                "provider_message_id": max_provider_message_id(existing_payload),
            }
        return {
            "send_state": "failed" if existing_status in {"failed", "dead"} else "queued",
            "status": "duplicate_pending",
        }

    adapter = await ensure_max_adapter(settings=settings)
    if adapter is None:
        await mark_max_message_retryable_failure(
            queued_message_id,
            attempted_at=now,
            error="adapter_unavailable",
            next_retry_at=compute_max_delivery_next_retry_at(
                attempt=1,
                retry_base_seconds=settings.max_delivery_recovery_retry_base_seconds,
                retry_max_seconds=settings.max_delivery_recovery_retry_max_seconds,
                now=now,
            ),
            attempts=1,
        )
        await _persist_send_attempt_state(
            token_id=token_id,
            launch_url=launch_url,
            chat_url=chat_url,
            text=text,
            send_state="failed",
            last_error_code="adapter_unavailable",
        )
        return {"send_state": "failed", "status": "adapter_unavailable"}

    send_result = await adapter.send_message(
        max_user_id,
        text,
        buttons=buttons or None,
        correlation_id=correlation_id,
    )

    async with async_session() as session:
        async with session.begin():
            message = await session.get(ChatMessage, queued_message_id)
            token = await session.get(CandidateAccessToken, token_id)
            if message is None or token is None:
                return {"send_state": "failed", "status": "message_or_token_missing"}
            if send_result.success:
                payload = dict(message.payload_json or {})
                payload["provider_message_id"] = send_result.message_id
                message.payload_json = payload
                message.status = ChatMessageStatus.SENT.value
                message.error = None
                message.delivery_attempts = max(1, int(message.delivery_attempts or 0) + 1)
                message.delivery_locked_at = None
                message.delivery_next_retry_at = None
                message.delivery_last_attempt_at = now
                message.delivery_dead_at = None
                token.launch_payload_json = {
                    **_safe_launch_payload_snapshot(
                        existing=token.launch_payload_json,
                        launch_url=launch_url,
                        chat_url=chat_url,
                        message_preview=text,
                        send_state="sent",
                    ),
                    "send_state": "sent",
                    "last_message_id": send_result.message_id,
                    "last_sent_at": now.isoformat(),
                }
                event_type = ApplicationEventType.MESSAGE_SENT.value
                event_metadata = {
                    "chat_message_id": int(message.id),
                    "token_id": token_id,
                    "message_id": send_result.message_id,
                }
                send_state = "sent"
            else:
                message.status = ChatMessageStatus.FAILED.value
                message.error = str(send_result.error or "max_send_failed")
                message.delivery_attempts = 1
                message.delivery_locked_at = None
                message.delivery_next_retry_at = compute_max_delivery_next_retry_at(
                    attempt=1,
                    retry_base_seconds=settings.max_delivery_recovery_retry_base_seconds,
                    retry_max_seconds=settings.max_delivery_recovery_retry_max_seconds,
                    now=now,
                )
                message.delivery_last_attempt_at = now
                message.delivery_dead_at = None
                token.launch_payload_json = {
                    **_safe_launch_payload_snapshot(
                        existing=token.launch_payload_json,
                        launch_url=launch_url,
                        chat_url=chat_url,
                        message_preview=text,
                        send_state="failed",
                    ),
                    "send_state": "failed",
                    "last_error_code": str(send_result.error or "max_send_failed"),
                    "last_sent_at": now.isoformat(),
                }
                event_type = ApplicationEventType.MESSAGE_FAILED.value
                event_metadata = {
                    "chat_message_id": int(message.id),
                    "token_id": token_id,
                    "failure_code": str(send_result.error or "max_send_failed"),
                    "failure_class": "provider_error",
                }
                send_state = "failed"
            await _publish_event(
                session,
                ApplicationEventCommand(
                    producer_family="max_invite_delivery",
                    idempotency_key=f"{event_type}:{queued_message_id}",
                    event_type=event_type,
                    candidate_id=int(candidate.id),
                    source_system="admin_ui",
                    source_ref=f"chat_message:{queued_message_id}",
                    correlation_id=correlation_id,
                    occurred_at=now,
                    actor_type="admin",
                    actor_id=0,
                    channel=CandidateLaunchChannel.MAX.value,
                    metadata_json=event_metadata,
                ),
            )

    await log_audit_action(
        "max_invite_send",
        "candidate",
        candidate.id,
        changes={
            "token_id": token_id,
            "correlation_id": correlation_id,
            "send_state": send_state,
        },
    )
    return {"send_state": send_state, "status": send_state}


async def revoke_candidate_max_launch_invite(
    candidate_id: int,
    *,
    application_id: int | None,
    principal: Principal,
    settings: Settings | None = None,
) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    if not _rollout_enabled(resolved_settings):
        raise MaxInviteRolloutDisabledError("MAX rollout surface is disabled.")

    now = _utcnow()
    async with async_session() as session:
        async with session.begin():
            preview = await create_max_launch_invite(
                candidate_id,
                application_id,
                session=session,
                revoke_active=True,
                issued_by_type=principal.type,
                issued_by_id=str(principal.id),
                revoke_reason="operator_revoked",
            )
            revoked_token_ids = tuple(int(value) for value in preview.lifecycle.revoked_token_ids)
            await _revoke_related_access_sessions(
                session,
                token_ids=revoked_token_ids,
                now=now,
            )
            correlation_id = ""
            if revoked_token_ids:
                token = await session.get(CandidateAccessToken, revoked_token_ids[0])
                correlation_id = str(getattr(token, "correlation_id", "") or "")
            await _publish_event(
                session,
                ApplicationEventCommand(
                    producer_family="max_candidate_access",
                    idempotency_key=f"revoked:{candidate_id}:{','.join(str(value) for value in revoked_token_ids)}",
                    event_type=preview.lifecycle.event_type,
                    candidate_id=candidate_id,
                    application_id=application_id,
                    source_system="admin_ui",
                    source_ref=f"candidate:{candidate_id}:max_invite:revoke",
                    correlation_id=correlation_id or None,
                    occurred_at=now,
                    actor_type=principal.type,
                    actor_id=principal.id,
                    channel=CandidateLaunchChannel.MAX.value,
                    metadata_json={
                        "revoked_token_ids": list(revoked_token_ids),
                        "revocation_reason": "operator_revoked",
                    },
                ),
            )

        await log_audit_action(
            "max_invite_revoke",
            "candidate",
            candidate_id,
            changes={
                "application_id": application_id,
                "revoked_token_ids": list(revoked_token_ids),
            },
        )

    return {
        "status": "revoked",
        "invite_state": "revoked",
        "revoked_at": now,
        "access_token_id": revoked_token_ids[0] if revoked_token_ids else None,
        "correlation_id": correlation_id or None,
    }


async def get_candidate_max_rollout_summary(
    candidate_id: int,
    *,
    application_id: int | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return await build_candidate_max_rollout_summary(
        candidate_id,
        application_id=application_id,
        settings=settings,
    )


async def issue_candidate_max_rollout(
    candidate_id: int,
    *,
    principal: Principal,
    application_id: int | None = None,
    dry_run: bool = False,
    send: bool = False,
    reuse_policy: str = "reuse_active",
    settings: Settings | None = None,
) -> dict[str, Any]:
    result = await issue_candidate_max_launch_invite(
        MaxInviteIssueRequest(
            candidate_id=candidate_id,
            application_id=application_id,
            dry_run=dry_run,
            send=send,
            reuse_policy=reuse_policy,
            principal=principal,
        ),
        settings=settings,
    )
    result["summary"] = await build_candidate_max_rollout_summary(
        candidate_id,
        application_id=application_id,
        settings=settings,
    )
    return result


async def revoke_candidate_max_rollout(
    candidate_id: int,
    *,
    principal: Principal,
    application_id: int | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    result = await revoke_candidate_max_launch_invite(
        candidate_id,
        application_id=application_id,
        principal=principal,
        settings=settings,
    )
    result["summary"] = await build_candidate_max_rollout_summary(
        candidate_id,
        application_id=application_id,
        settings=settings,
    )
    return result
