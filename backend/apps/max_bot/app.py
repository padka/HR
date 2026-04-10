"""MAX bot application — FastAPI webhook server."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from backend.core.audit import AuditContext, log_audit_action
from backend.core.redis_factory import create_redis_client
from backend.core.settings import get_settings

from .candidate_flow import (
    extract_callback_user,
    extract_message_text,
    extract_message_user,
    process_bot_started,
    process_callback,
    process_text_message,
    send_outbound,
)

logger = logging.getLogger(__name__)

MAX_WEBHOOK_UPDATE_TYPES = [
    "bot_started",
    "message_created",
    "message_callback",
]
WEBHOOK_DEDUPE_TTL_SECONDS = 8 * 60 * 60
_ALLOW_MEMORY_WEBHOOK_DEDUPE_ENVS = {"development", "test"}

_webhook_dedupe_fallback: dict[str, float] = {}
_webhook_dedupe_redis_client: Any = None
_webhook_dedupe_redis_url = ""
_webhook_dedupe_redis_failed = False
_webhook_dedupe_last_error: str | None = None
_subscription_status: dict[str, Any] = {
    "status": "not_configured",
    "action": "pending",
}
_ALLOW_UNSET_WEBHOOK_SECRET_ENVS = {"development", "test"}


def _set_subscription_status(**kwargs: Any) -> None:
    global _subscription_status
    _subscription_status = kwargs


def _get_subscription_status() -> dict[str, Any]:
    return dict(_subscription_status)


def _is_public_https_url(value: str | None) -> bool:
    parsed = urlparse(str(value or "").strip())
    if parsed.scheme.lower() != "https":
        return False
    normalized_host = str(parsed.hostname or "").strip().lower().strip("[]")
    return normalized_host not in {"", "localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _cleanup_dedupe_fallback(now: float) -> None:
    expired_before = now - WEBHOOK_DEDUPE_TTL_SECONDS
    for key, created_at in list(_webhook_dedupe_fallback.items()):
        if created_at <= expired_before:
            _webhook_dedupe_fallback.pop(key, None)


@dataclass(frozen=True)
class WebhookDedupeClaim:
    dedupe_key: str | None
    mode: str
    token: str | None = None


class WebhookDedupeUnavailable(RuntimeError):
    """Raised when production-grade dedupe storage is unavailable."""


def _dedupe_requires_redis(settings) -> bool:
    environment = str(getattr(settings, "environment", "") or "").strip().lower()
    return environment not in _ALLOW_MEMORY_WEBHOOK_DEDUPE_ENVS


async def _get_dedupe_redis_client(settings) -> Any:
    global _webhook_dedupe_last_error
    global _webhook_dedupe_redis_client, _webhook_dedupe_redis_failed, _webhook_dedupe_redis_url

    if settings.environment == "test":
        return None

    redis_url = (settings.redis_url or "").strip()
    if not redis_url:
        return None

    if _webhook_dedupe_redis_client is not None and _webhook_dedupe_redis_url == redis_url:
        return _webhook_dedupe_redis_client
    if _webhook_dedupe_redis_failed and _webhook_dedupe_redis_url == redis_url:
        return None

    try:
        client = create_redis_client(
            redis_url,
            component="max_webhook_dedupe",
            decode_responses=True,
        )
        await client.ping()
    except Exception as exc:
        _webhook_dedupe_redis_client = None
        _webhook_dedupe_redis_url = redis_url
        _webhook_dedupe_redis_failed = True
        _webhook_dedupe_last_error = str(exc)
        logger.warning("max_bot.webhook.dedupe.redis_unavailable", extra={"error": str(exc)})
        return None

    _webhook_dedupe_redis_client = client
    _webhook_dedupe_redis_url = redis_url
    _webhook_dedupe_redis_failed = False
    _webhook_dedupe_last_error = None
    return client


def _build_dedupe_key(raw_body: bytes, body: dict[str, Any]) -> str | None:
    update_type = str(body.get("update_type") or "").strip()
    callback = body.get("callback") or {}
    callback_id = str(callback.get("callback_id") or callback.get("id") or "").strip()
    if callback_id:
        return f"max:webhook:callback:{callback_id}"

    message = body.get("message") or {}
    message_id = (
        message.get("message_id")
        or message.get("mid")
        or (message.get("body") or {}).get("mid")
    )
    if message_id not in (None, ""):
        return f"max:webhook:message:{message_id}"

    delivery_marker = next(
        (
            str(value).strip()
            for value in (
                body.get("event_id"),
                body.get("update_id"),
                body.get("delivery_id"),
                body.get("timestamp"),
                body.get("ts"),
                callback.get("timestamp"),
                callback.get("created_at"),
                message.get("timestamp"),
                message.get("created_at"),
                (message.get("body") or {}).get("timestamp"),
                (message.get("body") or {}).get("created_at"),
            )
            if value not in (None, "")
            and str(value).strip()
        ),
        "",
    )
    digest = hashlib.sha256(raw_body).hexdigest()
    if delivery_marker:
        event_name = update_type or "unknown"
        return f"max:webhook:{event_name}:transport:{delivery_marker}:{digest}"

    if update_type in {"message_created", "message_callback"}:
        return None

    return f"max:webhook:body:{digest}"


async def _dedupe_health_status(settings) -> dict[str, Any]:
    redis_url = str(getattr(settings, "redis_url", "") or "").strip()
    client = await _get_dedupe_redis_client(settings)
    if client is not None:
        return {
            "ready": True,
            "mode": "redis",
            "requires_redis": _dedupe_requires_redis(settings),
            "error": None,
            "message": None,
        }
    if _dedupe_requires_redis(settings):
        error = "max_webhook_dedupe_redis_missing" if not redis_url else "max_webhook_dedupe_redis_unavailable"
        message = (
            "MAX webhook blocked until Redis-backed dedupe is available."
            if redis_url
            else "MAX webhook blocked until REDIS_URL is configured for dedupe."
        )
        return {
            "ready": False,
            "mode": "unavailable",
            "requires_redis": True,
            "error": error,
            "message": message,
        }
    return {
        "ready": True,
        "mode": "memory",
        "requires_redis": False,
        "error": None,
        "message": None,
    }


async def _claim_event_processing(
    settings,
    raw_body: bytes,
    body: dict[str, Any],
) -> WebhookDedupeClaim | None:
    global _webhook_dedupe_last_error
    dedupe_key = _build_dedupe_key(raw_body, body)
    if not dedupe_key:
        return WebhookDedupeClaim(dedupe_key=None, mode="none")
    client = await _get_dedupe_redis_client(settings)
    if client is not None:
        claim_token = secrets.token_hex(16)
        try:
            claimed = await client.set(
                dedupe_key,
                claim_token,
                ex=WEBHOOK_DEDUPE_TTL_SECONDS,
                nx=True,
            )
            return WebhookDedupeClaim(dedupe_key=dedupe_key, mode="redis", token=claim_token) if claimed else None
        except Exception as exc:
            _webhook_dedupe_last_error = str(exc)
            logger.warning("max_bot.webhook.dedupe.redis_unavailable", extra={"error": str(exc)})
            if _dedupe_requires_redis(settings):
                raise WebhookDedupeUnavailable("max_webhook_dedupe_redis_unavailable") from exc

    if _dedupe_requires_redis(settings):
        redis_url = str(getattr(settings, "redis_url", "") or "").strip()
        reason = "max_webhook_dedupe_redis_missing" if not redis_url else "max_webhook_dedupe_redis_unavailable"
        raise WebhookDedupeUnavailable(reason)

    now = time.time()
    _cleanup_dedupe_fallback(now)
    if dedupe_key in _webhook_dedupe_fallback:
        return None
    _webhook_dedupe_fallback[dedupe_key] = now
    return WebhookDedupeClaim(dedupe_key=dedupe_key, mode="memory")


async def _release_event_claim(settings, claim: WebhookDedupeClaim | None) -> None:
    if claim is None or not claim.dedupe_key or claim.mode == "none":
        return
    if claim.mode == "memory":
        _webhook_dedupe_fallback.pop(claim.dedupe_key, None)
        return
    client = await _get_dedupe_redis_client(settings)
    if client is None:
        return
    try:
        current_token = await client.get(claim.dedupe_key)
        if current_token == claim.token:
            await client.delete(claim.dedupe_key)
    except Exception as exc:
        logger.warning("max_bot.webhook.dedupe.release_failed", extra={"error": str(exc)})


async def _reject_dedupe_unavailable(request: Request, reason: str) -> JSONResponse:
    logger.error("max_bot.webhook.dedupe_unavailable", extra={"reason": reason})
    await log_audit_action(
        "max_webhook_rejected",
        "system",
        "max_bot",
        changes={"reason": reason},
        ctx=AuditContext(
            username="max_bot:webhook",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        ),
    )
    return JSONResponse({"error": "dedupe_unavailable", "reason": reason}, status_code=503)


def _reset_dedupe_state() -> None:
    global _webhook_dedupe_last_error
    global _webhook_dedupe_redis_client, _webhook_dedupe_redis_failed, _webhook_dedupe_redis_url
    _webhook_dedupe_fallback.clear()
    _webhook_dedupe_redis_client = None
    _webhook_dedupe_redis_url = ""
    _webhook_dedupe_redis_failed = False
    _webhook_dedupe_last_error = None


async def _claim_or_reject_dedupe(
    *,
    request: Request,
    settings,
    raw_body: bytes,
    body: dict[str, Any],
) -> WebhookDedupeClaim | JSONResponse | None:
    try:
        return await _claim_event_processing(settings, raw_body, body)
    except WebhookDedupeUnavailable as exc:
        return await _reject_dedupe_unavailable(request, str(exc))


def _get_max_adapter():
    from backend.core.messenger.protocol import MessengerPlatform
    from backend.core.messenger.registry import get_registry

    return get_registry().get(MessengerPlatform.MAX)


def _subscription_matches(subscription: dict[str, Any], *, url: str, secret: str) -> bool:
    subscription_url = str(subscription.get("url") or "").strip()
    if subscription_url != url:
        return False
    subscription_types = {
        str(item).strip()
        for item in (subscription.get("update_types") or [])
        if str(item).strip()
    }
    expected_types = set(MAX_WEBHOOK_UPDATE_TYPES)
    if subscription_types and subscription_types != expected_types:
        return False
    subscription_secret = str(subscription.get("secret") or "").strip()
    if secret and subscription_secret and subscription_secret != secret:
        return False
    return True


async def _reconcile_webhook_subscription(settings) -> None:
    webhook_url = getattr(settings, "max_webhook_url", "").strip()
    if not webhook_url:
        logger.warning("max_bot.subscription.skipped", extra={"reason": "missing_webhook_url"})
        _set_subscription_status(status="skipped", action="missing_webhook_url")
        return

    adapter = _get_max_adapter()
    if adapter is None or not hasattr(adapter, "list_subscriptions"):
        logger.error("max_bot.subscription.failed", extra={"reason": "adapter_not_ready"})
        _set_subscription_status(status="failed", action="adapter_not_ready")
        return

    webhook_secret = getattr(settings, "max_webhook_secret", "").strip()
    subscriptions = await adapter.list_subscriptions()
    matching_url = [
        item for item in subscriptions
        if str(item.get("url") or "").strip() == webhook_url
    ]
    stale_urls = sorted(
        {
            str(item.get("url") or "").strip()
            for item in subscriptions
            if str(item.get("url") or "").strip() and str(item.get("url") or "").strip() != webhook_url
        }
    )

    for stale_url in stale_urls:
        delete_result = await adapter.delete_subscription(url=stale_url)
        if not delete_result.success:
            logger.error(
                "max_bot.subscription.delete_failed",
                extra={"url": stale_url, "error": delete_result.error},
            )
            _set_subscription_status(
                status="failed",
                action="delete_failed",
                url=stale_url,
                error=delete_result.error,
            )
            return

    if len(matching_url) == 1 and _subscription_matches(
        matching_url[0],
        url=webhook_url,
        secret=webhook_secret,
    ):
        action = "kept" if not stale_urls else "pruned_stale"
        logger.info("max_bot.subscription.reconciled", extra={"action": action, "url": webhook_url})
        _set_subscription_status(status="ready", action=action, url=webhook_url)
        return

    if matching_url:
        delete_result = await adapter.delete_subscription(url=webhook_url)
        if not delete_result.success:
            logger.error(
                "max_bot.subscription.delete_failed",
                extra={"url": webhook_url, "error": delete_result.error},
            )
            _set_subscription_status(
                status="failed",
                action="delete_failed",
                url=webhook_url,
                error=delete_result.error,
            )
            return

    create_result = await adapter.create_subscription(
        url=webhook_url,
        update_types=list(MAX_WEBHOOK_UPDATE_TYPES),
        secret=webhook_secret or None,
    )
    if create_result.success:
        action = "recreated" if matching_url else "created"
        logger.info("max_bot.subscription.reconciled", extra={"action": action, "url": webhook_url})
        _set_subscription_status(status="ready", action=action, url=webhook_url)
        return

    logger.error(
        "max_bot.subscription.create_failed",
        extra={"url": webhook_url, "error": create_result.error},
    )
    _set_subscription_status(
        status="failed",
        action="create_failed",
        url=webhook_url,
        error=create_result.error,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: bootstrap messenger adapters on startup."""
    settings = get_settings()
    try:
        from backend.core.messenger.bootstrap import bootstrap_messenger_adapters

        await bootstrap_messenger_adapters(
            max_bot_enabled=settings.max_bot_enabled,
            max_bot_token=settings.max_bot_token,
        )
    except Exception:
        logger.exception("max_bot: failed to bootstrap messenger adapters")

    if settings.max_bot_enabled and settings.max_bot_token:
        try:
            await _reconcile_webhook_subscription(settings)
        except Exception:
            logger.exception("max_bot: failed to reconcile webhook subscription")
            _set_subscription_status(status="failed", action="reconcile_exception")

    yield

    try:
        adapter = _get_max_adapter()
        if adapter is not None:
            await adapter.close()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Create the MAX bot FastAPI application."""
    app = FastAPI(
        title="RecruiterSmart Max Bot",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_api_route("/webhook", webhook_handler, methods=["POST"])
    app.add_api_route("/health", health_check, methods=["GET"])

    return app


def _verify_secret(
    request_secret: str | None,
    expected_secret: str,
    *,
    allow_unset: bool = False,
) -> bool:
    """Verify the X-Max-Bot-Api-Secret header."""
    if not expected_secret:
        return allow_unset
    return secrets.compare_digest(request_secret or "", expected_secret)


def _webhook_secret_status(settings) -> dict[str, Any]:
    environment = str(getattr(settings, "environment", "") or "").strip().lower()
    expected_secret = str(getattr(settings, "max_webhook_secret", "") or "").strip()
    allow_unset = environment in _ALLOW_UNSET_WEBHOOK_SECRET_ENVS
    configured = bool(expected_secret)
    blocking = not configured and not allow_unset
    return {
        "configured": configured,
        "allow_unset": allow_unset,
        "blocking": blocking,
        "error": "max_webhook_secret_missing" if blocking else None,
        "message": (
            "MAX_WEBHOOK_SECRET должен быть задан вне development/test."
            if blocking
            else None
        ),
    }


async def _answer_callback(callback_id: str, notification: str = "Принято") -> None:
    adapter = _get_max_adapter()
    if adapter is None or not hasattr(adapter, "answer_callback"):
        return
    try:
        result = await adapter.answer_callback(callback_id, notification=notification)
    except Exception:
        logger.exception("max_bot.callback.answer_failed")
        return
    if result.success:
        logger.info("max_bot.callback.answered")
        return
    logger.warning(
        "max_bot.callback.answer_failed",
        extra={"error": result.error},
    )


async def webhook_handler(
    request: Request,
    x_max_bot_api_secret: str | None = Header(None),
) -> JSONResponse:
    """Handle incoming webhook events from MAX Bot API."""
    settings = get_settings()
    webhook_secret = getattr(settings, "max_webhook_secret", "")
    secret_status = _webhook_secret_status(settings)

    if secret_status["blocking"]:
        logger.error("max_bot.webhook.secret_missing")
        await log_audit_action(
            "max_webhook_rejected",
            "system",
            "max_bot",
            changes={"reason": "max_webhook_secret_missing"},
            ctx=AuditContext(
                username="max_bot:webhook",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            ),
        )
        return JSONResponse({"error": "max_webhook_secret_missing"}, status_code=503)

    if not _verify_secret(
        x_max_bot_api_secret,
        webhook_secret,
        allow_unset=bool(secret_status["allow_unset"]),
    ):
        logger.warning("max_bot.webhook.secret_reject")
        return JSONResponse({"error": "invalid_secret"}, status_code=403)

    raw_body = await request.body()
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    claim_result = await _claim_or_reject_dedupe(
        request=request,
        settings=settings,
        raw_body=raw_body,
        body=body,
    )
    if isinstance(claim_result, JSONResponse):
        return claim_result
    if claim_result is None:
        logger.info("max_bot.webhook.dedupe_hit")
        return JSONResponse({"ok": True, "duplicate": True})
    dedupe_claim = claim_result

    update_type = body.get("update_type", "")

    logger.info(
        "max_bot.webhook.received",
        extra={"update_type": update_type},
    )

    try:
        if update_type == "bot_started":
            await _handle_bot_started(body)
        elif update_type == "message_created":
            await _handle_message_created(body)
        elif update_type == "message_callback":
            await _handle_message_callback(body)
        else:
            logger.debug(
                "max_bot.webhook.unknown_type",
                extra={"update_type": update_type},
            )
    except Exception:
        logger.exception(
            "max_bot.webhook.handler_error",
            extra={"update_type": update_type},
        )
        await _release_event_claim(settings, dedupe_claim)
        return JSONResponse({"error": "handler_failed"}, status_code=500)

    return JSONResponse({"ok": True})


async def _handle_bot_started(event: dict[str, Any]) -> None:
    user_info = event.get("user", {})
    chat_id = event.get("chat_id")
    max_user_id = user_info.get("user_id") or chat_id

    if not max_user_id:
        logger.warning("max_bot.bot_started: no user_id in event")
        return

    user_name = user_info.get("name", "")

    logger.info("max_bot.bot_started")

    messages = await process_bot_started(
        max_user_id=str(max_user_id),
        display_name=user_name,
        start_payload=event.get("payload"),
    )
    await send_outbound(max_user_id=max_user_id, messages=messages)


async def _handle_message_created(event: dict[str, Any]) -> None:
    text = extract_message_text(event)
    max_user_id, user_name = extract_message_user(event)

    if not max_user_id or not text:
        return

    logger.info("max_bot.message_created")

    messages = await process_text_message(
        max_user_id=str(max_user_id),
        text=text,
        display_name=user_name,
        start_payload=event.get("payload"),
        raw_event=event,
    )
    await send_outbound(max_user_id=str(max_user_id), messages=messages)


async def _handle_message_callback(event: dict[str, Any]) -> None:
    callback = event.get("callback", {})
    callback_id = str(callback.get("callback_id") or callback.get("id") or "").strip()
    payload = callback.get("payload", "")
    max_user_id, _ = extract_callback_user(event)

    if not max_user_id or not payload:
        if callback_id:
            await _answer_callback(callback_id)
        return

    processed = False
    try:
        messages = await process_callback(
            max_user_id=str(max_user_id),
            payload=str(payload),
        )
        await send_outbound(max_user_id=str(max_user_id), messages=messages)
        processed = True
    finally:
        if callback_id and processed:
            await _answer_callback(callback_id)


def _runtime_guardrails(settings) -> dict[str, Any]:
    return {
        "public_entry_enabled": bool(getattr(settings, "max_bot_allow_public_entry", False)),
        "browser_portal_fallback_allowed": True,
        "telegram_business_fallback_allowed": False,
        "shared_contract_mode": "candidate_portal",
    }


def _build_readiness_blockers(
    *,
    settings,
    secret_status: dict[str, Any],
    dedupe_status: dict[str, Any],
    webhook_url_public_ready: bool,
    subscription_status: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    environment = str(getattr(settings, "environment", "") or "").strip().lower()
    webhook_url = str(getattr(settings, "max_webhook_url", "") or "").strip()
    if environment not in _ALLOW_UNSET_WEBHOOK_SECRET_ENVS:
        if not webhook_url:
            blockers.append("max_webhook_url_missing")
        elif not webhook_url_public_ready:
            blockers.append("max_webhook_url_not_public_https")
    if secret_status.get("error"):
        blockers.append(str(secret_status["error"]))
    if dedupe_status.get("error"):
        blockers.append(str(dedupe_status["error"]))
    subscription_state = str(subscription_status.get("status") or "").strip().lower()
    subscription_error = str(subscription_status.get("error") or "").strip()
    subscription_action = str(subscription_status.get("action") or "").strip()
    if subscription_error:
        blockers.append(subscription_error)
    elif subscription_state == "failed":
        blockers.append(f"max_subscription_{subscription_action or 'failed'}")
    return list(dict.fromkeys(item for item in blockers if item))


async def get_runtime_health_snapshot(settings=None) -> dict[str, Any]:
    """Return MAX runtime health and rollout guardrails without mutating state."""
    settings = settings or get_settings()
    adapter = _get_max_adapter()
    enabled = bool(getattr(settings, "max_bot_enabled", False))
    adapter_ready = bool(getattr(adapter, "is_ready", False)) if adapter is not None else False
    secret_status = _webhook_secret_status(settings)
    dedupe_status = await _dedupe_health_status(settings)
    webhook_url = str(getattr(settings, "max_webhook_url", "") or "").strip()
    webhook_url_public_ready = _is_public_https_url(webhook_url)
    subscription_status = _get_subscription_status()
    environment = str(getattr(settings, "environment", "") or "").strip().lower()
    guardrails = _runtime_guardrails(settings)
    if not enabled:
        return {
            "status": "disabled",
            "service": "max_bot",
            "enabled": False,
            "adapter_ready": adapter_ready,
            "runtime_ready": True,
            "webhook_url": webhook_url or None,
            "webhook_url_configured": bool(webhook_url),
            "webhook_url_public_ready": webhook_url_public_ready,
            "webhook_secret_configured": bool(secret_status["configured"]),
            "webhook_secret_error": None,
            "webhook_secret_message": "MAX runtime disabled by MAX_BOT_ENABLED=false.",
            "dedupe_ready": True,
            "dedupe_mode": "disabled",
            "dedupe_requires_redis": bool(dedupe_status["requires_redis"]),
            "dedupe_error": None,
            "dedupe_message": "MAX runtime disabled by feature flag.",
            "dedupe_last_error": _webhook_dedupe_last_error,
            "subscription_status": subscription_status,
            "subscription_ready": False,
            "readiness_blockers": [],
            **guardrails,
        }
    health_blocking = bool(secret_status["blocking"] or not dedupe_status["ready"])
    if environment not in _ALLOW_UNSET_WEBHOOK_SECRET_ENVS and not webhook_url_public_ready:
        health_blocking = True
    readiness_blockers = _build_readiness_blockers(
        settings=settings,
        secret_status=secret_status,
        dedupe_status=dedupe_status,
        webhook_url_public_ready=webhook_url_public_ready,
        subscription_status=subscription_status,
    )
    health_status = "blocked" if health_blocking else "ok"
    return {
        "status": health_status,
        "service": "max_bot",
        "enabled": enabled,
        "adapter_ready": adapter_ready,
        "runtime_ready": not health_blocking,
        "webhook_url": webhook_url or None,
        "webhook_url_configured": bool(webhook_url),
        "webhook_url_public_ready": webhook_url_public_ready,
        "webhook_secret_configured": bool(secret_status["configured"]),
        "webhook_secret_error": secret_status["error"],
        "webhook_secret_message": secret_status["message"],
        "dedupe_ready": bool(dedupe_status["ready"]),
        "dedupe_mode": dedupe_status["mode"],
        "dedupe_requires_redis": bool(dedupe_status["requires_redis"]),
        "dedupe_error": dedupe_status["error"],
        "dedupe_message": dedupe_status["message"],
        "dedupe_last_error": _webhook_dedupe_last_error,
        "subscription_status": subscription_status,
        "subscription_ready": str(subscription_status.get("status") or "").strip().lower() == "ready",
        "readiness_blockers": readiness_blockers,
        **guardrails,
    }


async def health_check() -> JSONResponse:
    """Health check endpoint with adapter/subscription visibility."""
    payload = await get_runtime_health_snapshot()
    status_code = 503 if payload["status"] == "blocked" else 200
    return JSONResponse(payload, status_code=status_code)
