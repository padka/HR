"""Shared Telegram/MAX reliability helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from backend.core.settings import get_settings


@dataclass(frozen=True)
class DeliveryFailure:
    failure_class: str
    failure_code: str
    degraded_reason: str | None = None


_PERMANENT_MARKERS = {
    "telegram_unauthorized": "blocked_user",
    "blocked": "blocked_user",
    "forbidden": "blocked_user",
    "chat_not_found": "invalid_recipient",
    "chat not found": "invalid_recipient",
    "invalid_recipient": "invalid_recipient",
    "not enough rights": "invalid_recipient",
}

_MISCONFIG_MARKERS = {
    "adapter_missing": "adapter_missing",
    "invalid token": "invalid_token",
    "unauthorized": "invalid_token",
    "max_bot_disabled": "channel_disabled",
    "webhook": "webhook_configuration",
    "bot_not_configured": "channel_disabled",
}


def classify_delivery_failure(*, channel: str, error: str | None) -> DeliveryFailure:
    normalized_channel = str(channel or "telegram").strip().lower() or "telegram"
    normalized_error = str(error or "unknown_error").strip().lower()

    if not normalized_error:
        return DeliveryFailure("transient", "unknown_error")

    for marker, code in _MISCONFIG_MARKERS.items():
        if marker in normalized_error:
            return DeliveryFailure(
                "misconfiguration",
                code,
                degraded_reason=f"{normalized_channel}:{code}",
            )

    for marker, code in _PERMANENT_MARKERS.items():
        if marker in normalized_error:
            return DeliveryFailure("permanent", code)

    if "429" in normalized_error or "rate limit" in normalized_error or "timeout" in normalized_error:
        return DeliveryFailure("transient", "rate_limited")
    if "5xx" in normalized_error or "server error" in normalized_error or "tempor" in normalized_error:
        return DeliveryFailure("transient", "provider_transient")
    if "network" in normalized_error or "connect" in normalized_error:
        return DeliveryFailure("transient", "network_error")

    return DeliveryFailure("transient", normalized_error.replace(" ", "_")[:64] or "unknown_error")


def default_max_public_entry_enabled() -> bool:
    settings = get_settings()
    return str(settings.environment or "").strip().lower() != "production"


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_channel_health_map(
    payload: Mapping[str, object] | None,
) -> dict[str, dict[str, object]]:
    state = dict(payload or {})
    normalized: dict[str, dict[str, object]] = {}
    for channel in ("telegram", "max"):
        raw = state.get(channel)
        if isinstance(raw, dict):
            normalized[channel] = dict(raw)
        else:
            normalized[channel] = {"status": "healthy", "reason": None, "updated_at": None}
    return normalized
