from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

try:  # pragma: no cover - optional dependency in some environments
    import httpx
except Exception:  # pragma: no cover - dependency checked at runtime
    httpx = None  # type: ignore[assignment]

from backend.core.messenger.bootstrap import describe_max_runtime_state
from backend.core.messenger.channel_state import (
    get_messenger_channel_health,
    get_messenger_channel_runtime,
    mark_messenger_channel_healthy,
    set_messenger_channel_degraded,
)
from backend.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

MAX_API_BASE = "https://platform-api.max.ru"
MAX_SYNC_TIMEOUT_SECONDS = 15.0


class MaxRuntimeSyncError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _channel_health_payload(channel_health: dict[str, object] | None) -> dict[str, object]:
    normalized = channel_health or {}
    status_value = str(normalized.get("status") or "healthy").strip().lower() or "healthy"
    return {
        "status": status_value,
        "degraded": status_value == "degraded",
        "reason": normalized.get("reason"),
        "updated_at": normalized.get("updated_at"),
    }


def _overall_status(*, runtime_status: str, channel_status: str) -> str:
    if channel_status == "degraded":
        return "degraded"
    if runtime_status == "configured":
        return "ok"
    if runtime_status == "not_registered":
        return "degraded"
    return runtime_status


def _normalize_profile(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": payload.get("user_id"),
        "username": payload.get("username"),
        "first_name": payload.get("first_name") or payload.get("name"),
        "description": payload.get("description"),
        "is_bot": payload.get("is_bot"),
        "last_activity_time": payload.get("last_activity_time"),
    }


def _normalize_subscription_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"value": str(item)}

    normalized: dict[str, Any] = {}
    url = item.get("url")
    if url is not None:
        normalized["url"] = str(url)

    raw_update_types = item.get("update_types")
    if isinstance(raw_update_types, list):
        normalized["update_types"] = [
            str(value)
            for value in raw_update_types
            if value is not None and str(value).strip()
        ]
    else:
        normalized["update_types"] = []

    if "secret" in item:
        normalized["secret_configured"] = bool(str(item.get("secret") or "").strip())

    for key in (
        "status",
        "state",
        "created_at",
        "updated_at",
        "last_error",
        "last_failure_at",
    ):
        value = item.get(key)
        if value is not None:
            normalized[key] = value

    return normalized


def _normalize_subscriptions(payload: dict[str, Any]) -> dict[str, Any]:
    raw_items = payload.get("subscriptions")
    items = raw_items if isinstance(raw_items, list) else []
    normalized_items = [_normalize_subscription_item(item) for item in items]
    return {
        "count": len(normalized_items),
        "items": normalized_items,
    }


def _request_error_message(payload: dict[str, Any], fallback: str) -> str:
    for key in ("description", "message", "error", "raw_text"):
        value = payload.get(key)
        if value:
            return str(value)
    return fallback


def _build_runtime_snapshot(
    *,
    settings: Settings,
    channel_health: dict[str, object] | None,
) -> dict[str, Any]:
    runtime = get_messenger_channel_runtime("max")
    health = _channel_health_payload(channel_health)
    runtime_status = str(runtime.get("status") or "disabled").strip().lower() or "disabled"
    return {
        "channel": "max",
        "status": _overall_status(
            runtime_status=runtime_status,
            channel_status=str(health["status"]),
        ),
        "message": describe_max_runtime_state(settings=settings),
        "runtime": {
            "status": runtime_status,
            "configured": bool(runtime.get("configured")),
            "registered": bool(runtime.get("registered")),
            "feature_enabled": bool(runtime.get("feature_enabled")),
            "invite_rollout_enabled": bool(runtime.get("invite_rollout_enabled")),
            "adapter": runtime.get("adapter"),
        },
        "channel_health": health,
        "config": {
            "adapter_enabled": bool(settings.max_adapter_enabled),
            "invite_rollout_enabled": bool(settings.max_invite_rollout_enabled),
            "bot_token_configured": bool(settings.max_bot_token),
            "bot_api_secret_configured": bool(
                getattr(settings, "max_bot_api_secret", "")
                or getattr(settings, "max_webhook_secret", "")
            ),
            "webhook_secret_configured": bool(
                getattr(settings, "max_bot_api_secret", "")
                or getattr(settings, "max_webhook_secret", "")
            ),
            "public_bot_name": settings.max_public_bot_name or None,
            "miniapp_url": settings.max_miniapp_url or None,
            "init_data_max_age_seconds": int(settings.max_init_data_max_age_seconds),
        },
    }


def _override_channel_health(
    payload: dict[str, Any],
    *,
    status: str,
    reason: str | None,
    updated_at: str,
) -> None:
    payload["channel_health"] = {
        "status": status,
        "degraded": status == "degraded",
        "reason": reason,
        "updated_at": updated_at,
    }
    runtime = payload.get("runtime") if isinstance(payload, dict) else {}
    runtime_status = (
        str(runtime.get("status") or "disabled").strip().lower()
        if isinstance(runtime, dict)
        else "disabled"
    )
    payload["status"] = _overall_status(
        runtime_status=runtime_status or "disabled",
        channel_status=status,
    )


async def get_max_runtime_snapshot(*, settings: Settings | None = None) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    health_map = await get_messenger_channel_health()
    return _build_runtime_snapshot(
        settings=resolved_settings,
        channel_health=health_map.get("max"),
    )


async def _request_json(
    client: Any,
    method: str,
    path: str,
) -> tuple[Any, dict[str, Any]]:
    response = await client.request(method, path)
    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": getattr(response, "text", "")}
    if not isinstance(payload, dict):
        payload = {"data": payload}
    return response, payload


async def sync_max_runtime_snapshot(
    *,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], int]:
    resolved_settings = settings or get_settings()
    checked_at = _utcnow().isoformat()
    degradable_codes = {"profile_probe_failed", "subscriptions_probe_failed"}

    try:
        if not resolved_settings.max_adapter_enabled:
            raise MaxRuntimeSyncError(
                "MAX adapter is disabled.",
                code="max_adapter_disabled",
                status_code=409,
            )
        if not str(resolved_settings.max_bot_token or "").strip():
            raise MaxRuntimeSyncError(
                "MAX bot token is not configured.",
                code="max_token_missing",
                status_code=503,
            )
        if httpx is None:
            raise MaxRuntimeSyncError(
                "MAX runtime sync client is unavailable.",
                code="http_client_unavailable",
                status_code=503,
            )

        async with httpx.AsyncClient(
            base_url=MAX_API_BASE,
            timeout=httpx.Timeout(MAX_SYNC_TIMEOUT_SECONDS),
            headers={
                "Accept": "application/json",
                "Authorization": str(resolved_settings.max_bot_token).strip(),
            },
        ) as client:
            profile_response, profile_payload = await _request_json(client, "GET", "/me")
            if not 200 <= profile_response.status_code < 300:
                raise MaxRuntimeSyncError(
                    _request_error_message(
                        profile_payload,
                        "MAX profile probe failed.",
                    ),
                    code="profile_probe_failed",
                    status_code=502,
                )

            subscriptions_response, subscriptions_payload = await _request_json(
                client,
                "GET",
                "/subscriptions",
            )
            if not 200 <= subscriptions_response.status_code < 300:
                raise MaxRuntimeSyncError(
                    _request_error_message(
                        subscriptions_payload,
                        "MAX subscriptions probe failed.",
                    ),
                    code="subscriptions_probe_failed",
                    status_code=502,
                )
    except MaxRuntimeSyncError as exc:
        if exc.code in degradable_codes:
            await set_messenger_channel_degraded("max", reason=f"max:{exc.code}")
        logger.warning("max runtime sync failed: %s", exc)
        payload = await get_max_runtime_snapshot(settings=resolved_settings)
        if exc.code in degradable_codes:
            _override_channel_health(
                payload,
                status="degraded",
                reason=f"max:{exc.code}",
                updated_at=checked_at,
            )
        payload["sync"] = {
            "ok": False,
            "checked_at": checked_at,
            "error": exc.code,
            "message": str(exc),
        }
        return payload, exc.status_code
    except Exception as exc:
        await set_messenger_channel_degraded("max", reason="max:sync_failed")
        logger.exception("max runtime sync crashed")
        payload = await get_max_runtime_snapshot(settings=resolved_settings)
        _override_channel_health(
            payload,
            status="degraded",
            reason="max:sync_failed",
            updated_at=checked_at,
        )
        payload["sync"] = {
            "ok": False,
            "checked_at": checked_at,
            "error": "sync_failed",
            "message": f"{exc.__class__.__name__}: {exc}",
        }
        return payload, 502

    await mark_messenger_channel_healthy("max")
    payload = await get_max_runtime_snapshot(settings=resolved_settings)
    _override_channel_health(
        payload,
        status="healthy",
        reason=None,
        updated_at=checked_at,
    )
    payload["sync"] = {
        "ok": True,
        "checked_at": checked_at,
        "profile": _normalize_profile(profile_payload),
        "subscriptions": _normalize_subscriptions(subscriptions_payload),
    }
    return payload, 200
