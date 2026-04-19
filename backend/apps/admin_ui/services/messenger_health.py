from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select

from backend.core.db import async_session
from backend.core.messenger.channel_state import (
    get_messenger_channel_health,
    get_messenger_channel_runtime,
    get_supported_messenger_channels,
)
from backend.domain.candidates.models import ChatMessage, ChatMessageDirection, User
from backend.domain.models import OutboxNotification


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _delivery_stage(status_value: str | None) -> str:
    normalized = str(status_value or "").strip().lower()
    if normalized == "queued":
        return "queued"
    if normalized == "sent":
        return "provider_accepted"
    if normalized == "failed":
        return "terminal_failed"
    return normalized or "unknown"


async def get_candidate_channel_health(candidate_id: int) -> dict[str, Any] | None:
    async with async_session() as session:
        candidate = await session.get(User, candidate_id)
        if candidate is None:
            return None

        last_inbound_at = await session.scalar(
            select(ChatMessage.created_at)
            .where(
                ChatMessage.candidate_id == candidate_id,
                ChatMessage.direction == ChatMessageDirection.INBOUND.value,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )

        last_outbound_message = await session.scalar(
            select(ChatMessage)
            .where(
                ChatMessage.candidate_id == candidate_id,
                ChatMessage.direction == ChatMessageDirection.OUTBOUND.value,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )

    preferred_channel = (
        str(getattr(candidate, "messenger_platform", "") or "").strip().lower()
    )
    if preferred_channel not in {"telegram", "max"}:
        preferred_channel = (
            "max"
            if getattr(candidate, "max_user_id", None)
            else "telegram"
            if (candidate.telegram_id or candidate.telegram_user_id)
            else None
        )

    source_value = str(getattr(candidate, "source", "") or "").strip().lower() or None
    source_labels = {
        "telegram": "Telegram",
        "bot": "Telegram",
        "max": "MAX",
        "hh": "HH.ru",
        "headhunter": "HH.ru",
        "manual": "Ручной ввод",
        "manual_call": "Ручной ввод",
        "manual_silent": "Ручной ввод",
        "candidate_access": "Candidate Access",
    }
    source_label = source_labels.get(
        source_value or "",
        (source_value or "Не указан").upper() if source_value else "Не указан",
    )
    linked_channels = {
        "telegram": bool(candidate.telegram_id or candidate.telegram_user_id),
        "max": bool(getattr(candidate, "max_user_id", None)),
    }

    return {
        "candidate_id": candidate_id,
        "source": source_value,
        "source_label": source_label,
        "preferred_channel": preferred_channel,
        "telegram_linked": linked_channels["telegram"],
        "max_linked": linked_channels["max"],
        "linked_channels": linked_channels,
        "telegram": {
            "linked": linked_channels["telegram"],
            "telegram_id": int(candidate.telegram_id)
            if candidate.telegram_id is not None
            else None,
            "telegram_username": candidate.telegram_username or candidate.username,
        },
        "max": {
            "linked": linked_channels["max"],
            "max_user_id": str(getattr(candidate, "max_user_id", "") or "").strip() or None,
        },
        "last_inbound_at": _iso(last_inbound_at),
        "last_outbound_at": _iso(
            last_outbound_message.created_at
            if last_outbound_message is not None
            else None
        ),
        "last_outbound_delivery": (
            {
                "status": str(last_outbound_message.status or "").strip().lower()
                or None,
                "delivery_stage": _delivery_stage(last_outbound_message.status),
                "error": last_outbound_message.error,
                "channel": str(last_outbound_message.channel or "").strip().lower()
                or None,
                "created_at": _iso(last_outbound_message.created_at),
            }
            if last_outbound_message is not None
            else None
        ),
    }


async def get_messenger_health(
    *,
    degraded_channels: dict[str, dict[str, Any]] | None = None,
    channels: Iterable[str] | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    channel_payloads: dict[str, dict[str, Any]] = {}
    degraded_channels = degraded_channels or {}
    channels = tuple(channels or get_supported_messenger_channels())

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
                select(func.min(OutboxNotification.created_at)).where(
                    OutboxNotification.messenger_channel == normalized_channel,
                    OutboxNotification.status == "pending",
                )
            )
            oldest_pending_age_seconds = None
            if oldest_pending is not None:
                if oldest_pending.tzinfo is None:
                    oldest_pending = oldest_pending.replace(tzinfo=UTC)
                oldest_pending_age_seconds = max(
                    0, int((now - oldest_pending).total_seconds())
                )

            degraded = degraded_channels.get(normalized_channel) or {}
            runtime = get_messenger_channel_runtime(normalized_channel)
            channel_payloads[normalized_channel] = {
                "channel": normalized_channel,
                "queue_depth": pending_count,
                "dead_letter_count": dead_letter_count,
                "oldest_pending_age_seconds": oldest_pending_age_seconds,
                "degraded": str(degraded.get("status") or "healthy") == "degraded",
                "status": runtime["status"],
                "runtime_status": runtime["status"],
                "configured": runtime["configured"],
                "registered": runtime["registered"],
                "feature_enabled": runtime["feature_enabled"],
                "adapter": runtime["adapter"],
                "degraded_reason": degraded.get("reason"),
                "degraded_at": degraded.get("updated_at"),
            }

    return {"channels": channel_payloads}


async def get_messenger_health_snapshot() -> dict[str, Any]:
    return await get_messenger_health(
        degraded_channels=await get_messenger_channel_health(),
    )
