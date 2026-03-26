from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import func, or_, select

from backend.core.db import async_session
from backend.core.messenger.channel_state import get_messenger_channel_health
from backend.domain.candidates.models import (
    CandidateInviteToken,
    CandidateJourneySession,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    User,
)
from backend.domain.candidates.portal_service import (
    build_candidate_public_max_mini_app_url,
    build_candidate_public_portal_url,
    get_candidate_active_slot,
    get_candidate_portal_max_entry_status,
    get_candidate_portal_public_status,
)
from backend.domain.models import OutboxNotification


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _delivery_stage(status_value: str | None) -> str:
    normalized = (status_value or "").strip().lower()
    if normalized == ChatMessageStatus.QUEUED.value:
        return "queued"
    if normalized == ChatMessageStatus.SENT.value:
        return "sent"
    if normalized == ChatMessageStatus.FAILED.value:
        return "failed"
    return normalized or "unknown"


def _serialize_invite(invite: CandidateInviteToken | None, *, candidate: User) -> dict[str, Any] | None:
    if invite is None:
        return None
    used_by = str(invite.used_by_external_id or "").strip() or None
    current_max = str(candidate.max_user_id or "").strip() or None
    return {
        "id": int(invite.id),
        "status": str(invite.status or "active"),
        "channel": str(invite.channel or "max"),
        "created_at": _iso(invite.created_at),
        "used_at": _iso(invite.used_at),
        "superseded_at": _iso(invite.superseded_at),
        "used_by_external_id": used_by,
        "conflict": bool(used_by and current_max and used_by != current_max),
    }


def _serialize_outbound_message(message: ChatMessage | None) -> dict[str, Any] | None:
    if message is None:
        return None
    return {
        "id": int(message.id),
        "channel": str(message.channel or "telegram"),
        "status": str(message.status or "unknown"),
        "delivery_stage": _delivery_stage(message.status),
        "error": message.error,
        "created_at": _iso(message.created_at),
        "author": message.author_label,
        "text": message.text or "",
    }


async def get_candidate_channel_health(candidate_id: int) -> dict[str, Any] | None:
    async with async_session() as session:
        candidate = await session.get(User, candidate_id)
        if candidate is None:
            return None

        latest_invite = None
        if candidate.candidate_id:
            latest_invite = await session.scalar(
                select(CandidateInviteToken)
                .where(
                    CandidateInviteToken.candidate_id == candidate.candidate_id,
                    CandidateInviteToken.channel == "max",
                )
                .order_by(CandidateInviteToken.created_at.desc(), CandidateInviteToken.id.desc())
                .limit(1)
            )

        last_inbound_at = await session.scalar(
            select(ChatMessage.created_at)
            .where(
                ChatMessage.candidate_id == candidate_id,
                ChatMessage.direction == ChatMessageDirection.INBOUND.value,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )
        last_outbound = await session.scalar(
            select(ChatMessage)
            .where(
                ChatMessage.candidate_id == candidate_id,
                ChatMessage.direction == ChatMessageDirection.OUTBOUND.value,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )
        active_journey = await session.scalar(
            select(CandidateJourneySession)
            .where(
                CandidateJourneySession.candidate_id == candidate_id,
                CandidateJourneySession.status == "active",
            )
            .order_by(CandidateJourneySession.id.desc())
            .limit(1)
        )
        active_slot = await get_candidate_active_slot(session, candidate)

    portal_status = get_candidate_portal_public_status()
    max_status = get_candidate_portal_max_entry_status()
    active_slot_status = str(getattr(active_slot, "status", "") or "").strip().lower()
    restart_allowed = active_slot_status not in {"confirmed", "confirmed_by_candidate"}
    config_errors = []
    if portal_status.get("message"):
        config_errors.append(str(portal_status["message"]))
    if max_status.get("message") and str(max_status["message"]) not in config_errors:
        config_errors.append(str(max_status["message"]))
    browser_link = None
    mini_app_link = None
    if active_journey is not None and candidate.candidate_id:
        browser_link = build_candidate_public_portal_url(
            candidate_uuid=str(candidate.candidate_id),
            entry_channel="max",
            source_channel="admin_health",
            journey_session_id=int(active_journey.id),
            session_version=int(active_journey.session_version or 1),
        )
        mini_app_link = build_candidate_public_max_mini_app_url(
            candidate_uuid=str(candidate.candidate_id),
            journey_session_id=int(active_journey.id),
            session_version=int(active_journey.session_version or 1),
            source_channel="admin_health",
        )

    return {
        "candidate_id": candidate_id,
        "preferred_channel": str(candidate.messenger_platform or "").strip() or None,
        "telegram": {
            "linked": bool(candidate.telegram_id or candidate.telegram_user_id),
            "telegram_id": int(candidate.telegram_id) if candidate.telegram_id is not None else None,
            "telegram_username": candidate.telegram_username or candidate.username,
        },
        "max": {
            "linked": bool(str(candidate.max_user_id or "").strip()),
            "max_user_id": str(candidate.max_user_id or "").strip() or None,
        },
        "active_invite": _serialize_invite(latest_invite, candidate=candidate),
        "last_inbound_at": _iso(last_inbound_at),
        "last_outbound": _serialize_outbound_message(last_outbound),
        "portal_public_url": portal_status.get("url"),
        "portal_entry_ready": bool(portal_status.get("ready")),
        "max_entry_ready": bool(max_status.get("ready")),
        "browser_link": browser_link or None,
        "mini_app_link": mini_app_link or None,
        "config_errors": config_errors,
        "active_journey_id": int(active_journey.id) if active_journey is not None else None,
        "session_version": int(active_journey.session_version or 1) if active_journey is not None else None,
        "last_link_issued_at": _iso(latest_invite.created_at) if latest_invite is not None else None,
        "restart_allowed": restart_allowed,
    }


async def get_messenger_health(
    *,
    degraded_channels: dict[str, dict[str, Any]] | None = None,
    channels: Iterable[str] = ("telegram", "max"),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    channel_payloads: dict[str, dict[str, Any]] = {}
    degraded_channels = degraded_channels or {}

    async with async_session() as session:
        for channel in channels:
            normalized_channel = str(channel).strip().lower()
            pending_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(OutboxNotification)
                    .where(
                        OutboxNotification.messenger_channel == normalized_channel,
                        OutboxNotification.status == "pending",
                    )
                )
                or 0
            )
            dead_letter_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(OutboxNotification)
                    .where(
                        OutboxNotification.messenger_channel == normalized_channel,
                        or_(
                            OutboxNotification.status == "dead_letter",
                            OutboxNotification.dead_lettered_at.is_not(None),
                        ),
                    )
                )
                or 0
            )
            oldest_pending = await session.scalar(
                select(func.min(OutboxNotification.created_at))
                .where(
                    OutboxNotification.messenger_channel == normalized_channel,
                    OutboxNotification.status == "pending",
                )
            )
            oldest_pending_age_seconds = None
            if oldest_pending is not None:
                if oldest_pending.tzinfo is None:
                    oldest_pending = oldest_pending.replace(tzinfo=timezone.utc)
                oldest_pending_age_seconds = max(0, int((now - oldest_pending).total_seconds()))

            degraded = degraded_channels.get(normalized_channel) or {}
            channel_payloads[normalized_channel] = {
                "channel": normalized_channel,
                "queue_depth": pending_count,
                "dead_letter_count": dead_letter_count,
                "oldest_pending_age_seconds": oldest_pending_age_seconds,
                "degraded": str(degraded.get("status") or "healthy") == "degraded",
                "degraded_reason": degraded.get("reason"),
                "degraded_at": degraded.get("updated_at"),
            }

    portal_status = get_candidate_portal_public_status()
    max_status = get_candidate_portal_max_entry_status()

    return {
        "channels": channel_payloads,
        "portal": {
            "public_url": portal_status.get("url"),
            "public_ready": bool(portal_status.get("ready")),
            "public_error": portal_status.get("error"),
            "public_message": portal_status.get("message"),
            "max_entry_ready": bool(max_status.get("ready")),
            "max_entry_error": max_status.get("error"),
            "max_entry_message": max_status.get("message"),
            "max_link_base": max_status.get("url"),
        },
    }


async def get_messenger_health_snapshot() -> dict[str, Any]:
    return await get_messenger_health(
        degraded_channels=await get_messenger_channel_health(),
    )
