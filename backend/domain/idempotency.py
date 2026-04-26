"""Shared idempotency helpers for bounded MAX messaging paths."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

MAX_IDEMPOTENCY_PREFIX = "max"
MAX_CLIENT_REQUEST_ID_LIMIT = 64
MAX_PROVIDER_SESSION_ID_LIMIT = 128


def _normalize_part(value: object) -> str:
    return str(value or "").strip()


def max_idempotency_key(scope: str, *parts: object, limit: int = MAX_CLIENT_REQUEST_ID_LIMIT) -> str:
    normalized_scope = _normalize_part(scope).lower().replace(" ", "-") or "event"
    normalized_parts = [_normalize_part(part) for part in parts if _normalize_part(part)]
    raw_key = ":".join([MAX_IDEMPOTENCY_PREFIX, normalized_scope, *normalized_parts])
    if len(raw_key) <= limit and raw_key.rstrip(":") != MAX_IDEMPOTENCY_PREFIX:
        return raw_key

    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    prefix = f"{MAX_IDEMPOTENCY_PREFIX}:{normalized_scope}:"
    digest_len = max(8, limit - len(prefix))
    if len(prefix) >= limit:
        prefix_digest = hashlib.sha256(prefix.encode("utf-8")).hexdigest()
        prefix = f"{MAX_IDEMPOTENCY_PREFIX}:id:{prefix_digest[:8]}:"
        digest_len = max(8, limit - len(prefix))
    return f"{prefix}{digest[:digest_len]}"


def max_webhook_outbound_key(kind: str, source_id: object) -> str:
    return max_idempotency_key(kind, source_id)


def max_bot_started_key(
    *,
    max_user_id: object,
    start_param: object = None,
) -> str:
    return max_idempotency_key("bot-started", max_user_id, start_param or "generic")


def max_bot_started_session_id(
    *,
    max_user_id: object,
    start_param: object = None,
) -> str:
    return max_idempotency_key(
        "bot-session",
        max_user_id,
        start_param or "generic",
        limit=MAX_PROVIDER_SESSION_ID_LIMIT,
    )


def max_webhook_inbound_message_key(
    *,
    provider_message_id: object,
    message_text: object,
    max_user_id: object,
) -> str:
    return max_idempotency_key("message", provider_message_id or message_text or max_user_id)


def max_chat_prompt_key(
    base_request_id: object,
    *,
    state: object,
    booking_id: object,
) -> str:
    return max_idempotency_key("chat-prompt", base_request_id, state, booking_id or "none")


def max_admin_chat_key(candidate_id: int, client_request_id: object) -> str | None:
    normalized = _normalize_part(client_request_id)
    if not normalized:
        return None
    return max_idempotency_key("admin-chat", candidate_id, normalized)


def max_rollout_invite_send_key(access_token_id: int) -> str:
    return max_idempotency_key("invite-send", access_token_id)


def max_provider_message_id(payload_json: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payload_json, Mapping):
        return None
    normalized = _normalize_part(payload_json.get("provider_message_id"))
    return normalized or None


def has_max_provider_boundary(
    *,
    status: object,
    payload_json: Mapping[str, Any] | None,
) -> bool:
    return _normalize_part(status).lower() == "sent" or max_provider_message_id(payload_json) is not None


__all__ = [
    "MAX_CLIENT_REQUEST_ID_LIMIT",
    "MAX_IDEMPOTENCY_PREFIX",
    "MAX_PROVIDER_SESSION_ID_LIMIT",
    "has_max_provider_boundary",
    "max_admin_chat_key",
    "max_bot_started_key",
    "max_bot_started_session_id",
    "max_chat_prompt_key",
    "max_idempotency_key",
    "max_provider_message_id",
    "max_rollout_invite_send_key",
    "max_webhook_inbound_message_key",
    "max_webhook_outbound_key",
]
