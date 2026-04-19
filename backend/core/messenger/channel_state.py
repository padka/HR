"""Persisted per-channel degraded state."""

from __future__ import annotations

import os

from backend.core.db import async_session
from backend.core.messenger.protocol import MessengerPlatform
from backend.core.messenger.reliability import normalize_channel_health_map, utc_iso_now
from backend.domain.models import BotRuntimeConfig

MESSENGER_CHANNEL_HEALTH_KEY = "messenger_channel_health"


def _get_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_bool_with_fallback(primary: str, fallback: str, *, default: bool) -> bool:
    raw = os.getenv(primary)
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    fallback_raw = os.getenv(fallback)
    if fallback_raw is not None:
        return fallback_raw.strip().lower() in {"1", "true", "yes", "on"}
    return default


def get_supported_messenger_channels() -> tuple[str, ...]:
    return tuple(platform.value for platform in MessengerPlatform)


def get_messenger_channel_runtime(channel: str) -> dict[str, object]:
    normalized_channel = str(channel or "telegram").strip().lower() or "telegram"
    try:
        platform = MessengerPlatform.from_str(normalized_channel)
    except ValueError:
        return {
            "channel": normalized_channel,
            "status": "disabled",
            "configured": False,
            "registered": False,
            "feature_enabled": False,
            "adapter": None,
        }

    feature_enabled = False
    env_configured = False
    invite_rollout_enabled = False
    if platform == MessengerPlatform.TELEGRAM:
        feature_enabled = _get_bool("BOT_ENABLED", default=True) or _get_bool(
            "ENABLE_TEST2_BOT",
            default=False,
        )
        env_configured = bool((os.getenv("BOT_TOKEN", "") or "").strip())
    elif platform == MessengerPlatform.MAX:
        feature_enabled = _get_bool_with_fallback(
            "MAX_ADAPTER_ENABLED",
            "MAX_BOT_ENABLED",
            default=False,
        )
        env_configured = bool((os.getenv("MAX_BOT_TOKEN", "") or "").strip())
        invite_rollout_enabled = _get_bool("MAX_INVITE_ROLLOUT_ENABLED", default=False)

    from backend.core.messenger.registry import get_registry

    adapter = get_registry().get(platform)
    registered = adapter is not None
    adapter_ready = (
        bool(getattr(adapter, "is_configured", registered)) if registered else False
    )

    if registered and adapter_ready:
        status = "configured"
    elif registered:
        status = "disabled"
    elif feature_enabled and env_configured:
        status = "not_registered"
    else:
        status = "disabled"

    return {
        "channel": normalized_channel,
        "status": status,
        "configured": env_configured or adapter_ready,
        "registered": registered,
        "feature_enabled": feature_enabled,
        "invite_rollout_enabled": invite_rollout_enabled,
        "adapter": adapter.__class__.__name__ if adapter is not None else None,
    }


async def get_messenger_channel_health() -> dict[str, dict[str, object]]:
    async with async_session() as session:
        row = await session.get(BotRuntimeConfig, MESSENGER_CHANNEL_HEALTH_KEY)
        payload = row.value_json if row and isinstance(row.value_json, dict) else {}
        normalized = normalize_channel_health_map(payload)
        for channel in get_supported_messenger_channels():
            normalized.setdefault(
                channel,
                {"status": "healthy", "reason": None, "updated_at": None},
            )
        return normalized


async def set_messenger_channel_degraded(channel: str, *, reason: str) -> None:
    normalized_channel = str(channel or "telegram").strip().lower() or "telegram"
    async with async_session() as session:
        async with session.begin():
            row = await session.get(
                BotRuntimeConfig, MESSENGER_CHANNEL_HEALTH_KEY, with_for_update=True
            )
            payload = normalize_channel_health_map(row.value_json if row else {})
            payload[normalized_channel] = {
                "status": "degraded",
                "reason": reason,
                "updated_at": utc_iso_now(),
            }
            if row is None:
                session.add(
                    BotRuntimeConfig(
                        key=MESSENGER_CHANNEL_HEALTH_KEY, value_json=payload
                    )
                )
            else:
                row.value_json = payload


async def mark_messenger_channel_healthy(channel: str) -> None:
    normalized_channel = str(channel or "telegram").strip().lower() or "telegram"
    async with async_session() as session:
        async with session.begin():
            row = await session.get(
                BotRuntimeConfig, MESSENGER_CHANNEL_HEALTH_KEY, with_for_update=True
            )
            payload = normalize_channel_health_map(row.value_json if row else {})
            payload[normalized_channel] = {
                "status": "healthy",
                "reason": None,
                "updated_at": utc_iso_now(),
            }
            if row is None:
                session.add(
                    BotRuntimeConfig(
                        key=MESSENGER_CHANNEL_HEALTH_KEY, value_json=payload
                    )
                )
            else:
                row.value_json = payload
