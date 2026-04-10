from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, or_, select

from backend.apps.admin_ui.services.candidate_shared_access import (
    get_candidate_shared_access_health,
)
from backend.apps.max_bot.app import get_runtime_health_snapshot
from backend.core.db import async_session
from backend.core.messenger.channel_state import get_messenger_channel_health
from backend.core.messenger.protocol import MessengerPlatform
from backend.core.messenger.registry import get_registry
from backend.core.settings import get_settings
from backend.domain.candidates.models import (
    CandidateInviteToken,
    CandidateJourneySession,
    ChatMessage,
    ChatMessageDirection,
    ChatMessageStatus,
    User,
)
from backend.domain.candidates.portal_service import (
    build_candidate_public_max_mini_app_url_async,
    build_candidate_public_portal_url,
    build_candidate_public_telegram_entry_url_async,
    build_candidate_shared_portal_url,
    get_candidate_active_slot,
    get_candidate_portal_max_entry_status_async,
    get_candidate_portal_public_status,
    get_candidate_portal_telegram_entry_status_async,
    inspect_max_bot_profile_probe,
)
from backend.domain.models import OutboxNotification


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
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


def _is_public_https_url(value: str | None) -> bool:
    parsed = urlparse(str(value or "").strip())
    if parsed.scheme.lower() != "https":
        return False
    normalized_host = str(parsed.hostname or "").strip().lower().strip("[]")
    return normalized_host not in {"", "localhost", "127.0.0.1", "::1", "0.0.0.0"}


async def _inspect_max_webhook_status() -> dict[str, Any]:
    settings = get_settings()
    environment = str(getattr(settings, "environment", "") or "").strip().lower()
    webhook_secret = str(settings.max_webhook_secret or "").strip()
    if not webhook_secret and environment not in {"development", "test"}:
        return {
            "webhook_public_ready": False,
            "webhook_url": str(settings.max_webhook_url or "").strip() or None,
            "webhook_error": "max_webhook_secret_missing",
            "webhook_message": "MAX_WEBHOOK_SECRET должен быть задан вне development/test.",
            "subscription_ready": False,
            "subscription_error": "max_webhook_secret_missing",
            "subscription_message": "MAX ingress заблокирован, пока не задан MAX_WEBHOOK_SECRET.",
        }
    webhook_url = str(settings.max_webhook_url or "").strip()
    if not _is_public_https_url(webhook_url):
        return {
            "webhook_public_ready": False,
            "webhook_url": webhook_url or None,
            "webhook_error": "max_webhook_unreachable",
            "webhook_message": "MAX_WEBHOOK_URL должен быть публичным HTTPS URL.",
            "subscription_ready": False,
            "subscription_error": "max_subscription_not_ready",
            "subscription_message": "Подписка webhook не может быть подтверждена без публичного URL.",
        }

    adapter = get_registry().get(MessengerPlatform.MAX)
    if adapter is None or not hasattr(adapter, "list_subscriptions"):
        return {
            "webhook_public_ready": True,
            "webhook_url": webhook_url,
            "webhook_error": None,
            "webhook_message": None,
            "subscription_ready": False,
            "subscription_error": "max_subscription_not_ready",
            "subscription_message": "MAX adapter не инициализирован.",
        }

    try:
        subscriptions = await adapter.list_subscriptions()
    except Exception as exc:
        return {
            "webhook_public_ready": True,
            "webhook_url": webhook_url,
            "webhook_error": None,
            "webhook_message": None,
            "subscription_ready": False,
            "subscription_error": "max_subscription_not_ready",
            "subscription_message": str(exc),
        }

    for item in subscriptions:
        if str(item.get("url") or "").strip() == webhook_url:
            return {
                "webhook_public_ready": True,
                "webhook_url": webhook_url,
                "webhook_error": None,
                "webhook_message": None,
                "subscription_ready": True,
                "subscription_error": None,
                "subscription_message": None,
            }
    return {
        "webhook_public_ready": True,
        "webhook_url": webhook_url,
        "webhook_error": None,
        "webhook_message": None,
        "subscription_ready": False,
        "subscription_error": "max_subscription_not_ready",
        "subscription_message": "Текущий MAX webhook не зарегистрирован у провайдера.",
    }


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
        recent_outbound = (
            await session.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.candidate_id == candidate_id,
                    ChatMessage.direction == ChatMessageDirection.OUTBOUND.value,
                )
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .limit(12)
            )
        ).all()
        last_outbound = recent_outbound[0] if recent_outbound else None
        last_portal_access = next(
            (
                message
                for message in recent_outbound
                if isinstance(message.payload_json, dict)
                and str(message.payload_json.get("kind") or "").strip() == "portal_access_package"
            ),
            None,
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
        last_entry_channel = None
        journey_meta = {}
        if active_journey is not None and isinstance(active_journey.payload_json, dict):
            journey_meta = dict(active_journey.payload_json)
            last_entry_channel = str(journey_meta.get("last_entry_channel") or "").strip() or None

    portal_status = get_candidate_portal_public_status()
    max_status = await get_candidate_portal_max_entry_status_async()
    telegram_status = await get_candidate_portal_telegram_entry_status_async()
    degraded_channels = await get_messenger_channel_health()
    max_channel_state = degraded_channels.get("max") or {}
    active_slot_status = str(getattr(active_slot, "status", "") or "").strip().lower()
    restart_allowed = active_slot_status not in {"confirmed", "confirmed_by_candidate"}
    config_errors = []
    if portal_status.get("message"):
        config_errors.append(str(portal_status["message"]))
    if max_status.get("message") and str(max_status["message"]) not in config_errors:
        config_errors.append(str(max_status["message"]))
    webhook_status = await _inspect_max_webhook_status()
    if webhook_status.get("webhook_message") and str(webhook_status["webhook_message"]) not in config_errors:
        config_errors.append(str(webhook_status["webhook_message"]))
    browser_link = None
    mini_app_link = None
    telegram_link = None
    if active_journey is not None and candidate.candidate_id:
        browser_link = build_candidate_public_portal_url(
            candidate_uuid=str(candidate.candidate_id),
            entry_channel="max",
            source_channel="admin_health",
            journey_session_id=int(active_journey.id),
            session_version=int(active_journey.session_version or 1),
        )
        mini_app_link = await build_candidate_public_max_mini_app_url_async(
            candidate_uuid=str(candidate.candidate_id),
            journey_session_id=int(active_journey.id),
            session_version=int(active_journey.session_version or 1),
            source_channel="admin_health",
        )
        async with async_session() as session:
            async with session.begin():
                telegram_link = await build_candidate_public_telegram_entry_url_async(
                    session,
                    candidate_uuid=str(candidate.candidate_id),
                )

    delivery_block_reason = None
    if not portal_status.get("ready"):
        delivery_block_reason = str(portal_status.get("error") or "candidate_portal_public_url_invalid")
    elif not max_status.get("ready"):
        delivery_block_reason = str(max_status.get("error") or "max_entry_blocked")
    elif not str(candidate.max_user_id or "").strip():
        delivery_block_reason = "max_not_linked"
    elif str(max_channel_state.get("status") or "").strip().lower() == "degraded":
        delivery_block_reason = str(max_channel_state.get("reason") or "max_channel_degraded")
    delivery_ready = delivery_block_reason is None
    shared_portal_ready = bool(portal_status.get("ready") and str(candidate.phone_normalized or "").strip())
    shared_portal_block_reason = None
    if not portal_status.get("ready"):
        shared_portal_block_reason = str(portal_status.get("error") or "candidate_portal_public_url_invalid")
    elif not str(candidate.phone_normalized or "").strip():
        shared_portal_block_reason = "shared_portal_phone_missing"

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
        "last_portal_access_delivery": _serialize_outbound_message(last_portal_access),
        "portal_public_url": portal_status.get("url"),
        "shared_portal_url": build_candidate_shared_portal_url(),
        "shared_portal_ready": shared_portal_ready,
        "shared_portal_block_reason": shared_portal_block_reason,
        "last_shared_portal_sent_at": journey_meta.get("shared_portal_last_sent_at"),
        "last_otp_delivery_channel": journey_meta.get("shared_portal_last_delivery_channel"),
        "public_link": str(max_status.get("url") or "").strip() or None,
        "portal_entry_ready": bool(portal_status.get("ready")),
        "max_entry_ready": bool(max_status.get("ready")),
        "telegram_entry_ready": bool(telegram_status.get("ready")),
        "token_valid": max_status.get("token_valid"),
        "bot_profile_resolved": bool(max_status.get("bot_profile_resolved")),
        "bot_profile_name": max_status.get("bot_profile_name"),
        "max_link_base_resolved": bool(max_status.get("max_link_base_resolved")),
        "max_link_base_source": max_status.get("max_link_base_source"),
        "browser_link": browser_link or None,
        "mini_app_link": mini_app_link or None,
        "telegram_link": telegram_link or None,
        "config_errors": config_errors,
        "active_journey_id": int(active_journey.id) if active_journey is not None else None,
        "session_version": int(active_journey.session_version or 1) if active_journey is not None else None,
        "last_entry_channel": last_entry_channel or (str(active_journey.entry_channel or "").strip() if active_journey is not None else None),
        "last_link_issued_at": _iso(latest_invite.created_at) if latest_invite is not None else None,
        "restart_allowed": restart_allowed,
        "delivery_ready": delivery_ready,
        "delivery_block_reason": delivery_block_reason,
        "degraded_channels": degraded_channels,
    }


async def get_messenger_health(
    *,
    degraded_channels: dict[str, dict[str, Any]] | None = None,
    channels: Iterable[str] = ("telegram", "max"),
) -> dict[str, Any]:
    now = datetime.now(UTC)
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
                    oldest_pending = oldest_pending.replace(tzinfo=UTC)
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
    max_status = await get_candidate_portal_max_entry_status_async()
    profile_probe = await inspect_max_bot_profile_probe()
    webhook_status = await _inspect_max_webhook_status()
    runtime_status = await get_runtime_health_snapshot()
    shared_access = await get_candidate_shared_access_health()

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
            "token_valid": profile_probe.get("token_valid"),
            "bot_profile_resolved": bool(profile_probe.get("bot_profile_resolved")),
            "bot_profile_name": profile_probe.get("bot_profile_name"),
            "max_link_base_resolved": bool(profile_probe.get("max_link_base_resolved")),
            "max_link_base_source": profile_probe.get("max_link_base_source"),
            "runtime_status": runtime_status.get("status"),
            "runtime_ready": bool(runtime_status.get("runtime_ready")),
            "adapter_ready": bool(runtime_status.get("adapter_ready")),
            "public_entry_enabled": bool(runtime_status.get("public_entry_enabled")),
            "webhook_url_public_ready": bool(runtime_status.get("webhook_url_public_ready")),
            "dedupe_ready": bool(runtime_status.get("dedupe_ready")),
            "dedupe_mode": runtime_status.get("dedupe_mode"),
            "dedupe_requires_redis": bool(runtime_status.get("dedupe_requires_redis")),
            "dedupe_error": runtime_status.get("dedupe_error"),
            "dedupe_message": runtime_status.get("dedupe_message"),
            "webhook_public_ready": webhook_status.get("webhook_public_ready"),
            "webhook_url": webhook_status.get("webhook_url"),
            "webhook_error": webhook_status.get("webhook_error"),
            "webhook_message": webhook_status.get("webhook_message"),
            "subscription_ready": webhook_status.get("subscription_ready"),
            "subscription_error": webhook_status.get("subscription_error"),
            "subscription_message": webhook_status.get("subscription_message"),
            "subscription_status": runtime_status.get("subscription_status"),
            "readiness_blockers": runtime_status.get("readiness_blockers") or [],
            "browser_portal_fallback_allowed": bool(runtime_status.get("browser_portal_fallback_allowed")),
            "telegram_business_fallback_allowed": bool(runtime_status.get("telegram_business_fallback_allowed")),
            "shared_contract_mode": runtime_status.get("shared_contract_mode"),
            "shared_access": shared_access,
        },
    }


async def get_messenger_health_snapshot() -> dict[str, Any]:
    return await get_messenger_health(
        degraded_channels=await get_messenger_channel_health(),
    )
