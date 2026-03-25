"""Persisted per-channel degraded state for Telegram/MAX."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from backend.core.db import async_session
from backend.core.messenger.reliability import normalize_channel_health_map, utc_iso_now
from backend.domain.models import BotRuntimeConfig

MESSENGER_CHANNEL_HEALTH_KEY = "messenger_channel_health"


async def get_messenger_channel_health() -> dict[str, dict[str, object]]:
    async with async_session() as session:
        row = await session.get(BotRuntimeConfig, MESSENGER_CHANNEL_HEALTH_KEY)
        payload = row.value_json if row and isinstance(row.value_json, dict) else {}
        return normalize_channel_health_map(payload)


async def set_messenger_channel_degraded(channel: str, *, reason: str) -> None:
    normalized_channel = str(channel or "telegram").strip().lower() or "telegram"
    async with async_session() as session:
        async with session.begin():
            row = await session.get(BotRuntimeConfig, MESSENGER_CHANNEL_HEALTH_KEY, with_for_update=True)
            payload = normalize_channel_health_map(row.value_json if row else {})
            payload[normalized_channel] = {
                "status": "degraded",
                "reason": reason,
                "updated_at": utc_iso_now(),
            }
            if row is None:
                session.add(BotRuntimeConfig(key=MESSENGER_CHANNEL_HEALTH_KEY, value_json=payload))
            else:
                row.value_json = payload


async def mark_messenger_channel_healthy(channel: str) -> None:
    normalized_channel = str(channel or "telegram").strip().lower() or "telegram"
    async with async_session() as session:
        async with session.begin():
            row = await session.get(BotRuntimeConfig, MESSENGER_CHANNEL_HEALTH_KEY, with_for_update=True)
            payload = normalize_channel_health_map(row.value_json if row else {})
            payload[normalized_channel] = {
                "status": "healthy",
                "reason": None,
                "updated_at": utc_iso_now(),
            }
            if row is None:
                session.add(BotRuntimeConfig(key=MESSENGER_CHANNEL_HEALTH_KEY, value_json=payload))
            else:
                row.value_json = payload
