"""Cross-process notifications for bot/admin content changes.

This module provides a tiny Redis pub/sub channel used to propagate "content changed"
events from admin_ui to the standalone bot process without requiring a restart.

Design goals:
- Best effort: publishing failures must not break admin flows.
- Low coupling: payload is small JSON; subscribers decide what to invalidate.
- Backward compatible: does not affect public HTTP API contracts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from backend.core.redis_factory import create_redis_client
from backend.core.settings import get_settings

logger = logging.getLogger(__name__)

# Public, stable channel name (shared by bot + admin_ui).
CONTENT_UPDATES_CHANNEL = "recruitsmart:content_updates"

# Event kinds (keep small; extend when needed).
KIND_QUESTIONS_CHANGED = "questions_changed"
KIND_TEMPLATES_CHANGED = "templates_changed"


@dataclass(frozen=True)
class ContentUpdateEvent:
    """Parsed content update event."""

    kind: str
    payload: Dict[str, Any]
    at: float


def build_content_update(kind: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Build JSON-encoded pub/sub payload."""

    return json.dumps(
        {
            "kind": str(kind or "").strip(),
            "payload": dict(payload or {}),
            "at": float(time.time()),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def parse_content_update(raw: str) -> Optional[ContentUpdateEvent]:
    """Parse JSON pub/sub payload. Returns None on invalid input."""

    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    kind = str(data.get("kind") or "").strip()
    if not kind:
        return None
    payload = data.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    try:
        at = float(data.get("at") or 0.0)
    except (TypeError, ValueError):
        at = 0.0
    return ContentUpdateEvent(kind=kind, payload=dict(payload), at=at)


async def publish_content_update(
    kind: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    channel: str = CONTENT_UPDATES_CHANNEL,
    timeout_seconds: float = 1.0,
) -> bool:
    """Publish a content update event to Redis (best effort).

    Returns:
        True if published successfully, False otherwise.
    """

    settings = get_settings()
    if getattr(settings, "environment", "") == "test":
        return False
    redis_url = getattr(settings, "redis_url", "") or ""
    if not redis_url:
        return False

    message = build_content_update(kind, payload)
    try:
        client = create_redis_client(redis_url, component="content_updates", decode_responses=True)
    except Exception:
        logger.debug("content_updates.redis_client_init_failed", exc_info=True)
        return False

    try:
        await asyncio.wait_for(client.publish(channel, message), timeout=timeout_seconds)
        return True
    except Exception:
        logger.debug(
            "content_updates.publish_failed",
            exc_info=True,
            extra={"kind": kind, "channel": channel},
        )
        return False
    finally:
        try:
            await client.close()
        except Exception:
            pass


async def run_content_updates_subscriber(
    *,
    redis_url: str,
    stop_event: asyncio.Event,
    on_event: Callable[[ContentUpdateEvent], Awaitable[None]],
    channel: str = CONTENT_UPDATES_CHANNEL,
    poll_timeout_seconds: float = 1.0,
) -> None:
    """Run a Redis pub/sub loop until stop_event is set.

    Notes:
    - Uses polling `pubsub.get_message()` to allow clean shutdown.
    - Reconnection/backoff should be handled by the caller (wrap this function).
    """

    client = create_redis_client(redis_url, component="content_updates_sub", decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)
    try:
        while not stop_event.is_set():
            msg = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=poll_timeout_seconds,
            )
            if msg is None:
                continue
            raw = msg.get("data")
            if not isinstance(raw, str):
                continue
            event = parse_content_update(raw)
            if event is None:
                continue
            try:
                await on_event(event)
            except Exception:
                logger.exception(
                    "content_updates.handler_failed",
                    extra={"kind": event.kind},
                )
    finally:
        try:
            await pubsub.unsubscribe(channel)
        except Exception:
            pass
        try:
            await pubsub.close()
        except Exception:
            pass
        try:
            await client.close()
        except Exception:
            pass


__all__ = [
    "CONTENT_UPDATES_CHANNEL",
    "ContentUpdateEvent",
    "KIND_QUESTIONS_CHANGED",
    "KIND_TEMPLATES_CHANGED",
    "build_content_update",
    "parse_content_update",
    "publish_content_update",
    "run_content_updates_subscriber",
]
