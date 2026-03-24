"""MAX bot application — FastAPI webhook server."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

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

_webhook_dedupe_fallback: dict[str, float] = {}
_webhook_dedupe_redis_client: Any = None
_webhook_dedupe_redis_url = ""
_webhook_dedupe_redis_failed = False
_subscription_status: dict[str, Any] = {
    "status": "not_configured",
    "action": "pending",
}


def _set_subscription_status(**kwargs: Any) -> None:
    global _subscription_status
    _subscription_status = kwargs


def _cleanup_dedupe_fallback(now: float) -> None:
    expired_before = now - WEBHOOK_DEDUPE_TTL_SECONDS
    for key, created_at in list(_webhook_dedupe_fallback.items()):
        if created_at <= expired_before:
            _webhook_dedupe_fallback.pop(key, None)


async def _get_dedupe_redis_client(settings) -> Any:
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
        logger.warning("max_bot.webhook.dedupe.redis_unavailable", extra={"error": str(exc)})
        return None

    _webhook_dedupe_redis_client = client
    _webhook_dedupe_redis_url = redis_url
    _webhook_dedupe_redis_failed = False
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

    if update_type == "message_created":
        return None

    digest = hashlib.sha256(raw_body).hexdigest()
    return f"max:webhook:body:{digest}"


async def _is_duplicate_event(settings, raw_body: bytes, body: dict[str, Any]) -> bool:
    dedupe_key = _build_dedupe_key(raw_body, body)
    if not dedupe_key:
        return False
    client = await _get_dedupe_redis_client(settings)
    if client is not None:
        try:
            existing = await client.get(dedupe_key)
            return bool(existing)
        except Exception as exc:
            logger.warning("max_bot.webhook.dedupe.redis_fallback", extra={"error": str(exc)})

    now = time.time()
    _cleanup_dedupe_fallback(now)
    return dedupe_key in _webhook_dedupe_fallback


async def _mark_event_processed(settings, raw_body: bytes, body: dict[str, Any]) -> None:
    dedupe_key = _build_dedupe_key(raw_body, body)
    if not dedupe_key:
        return
    client = await _get_dedupe_redis_client(settings)
    if client is not None:
        try:
            await client.set(
                dedupe_key,
                str(int(time.time())),
                ex=WEBHOOK_DEDUPE_TTL_SECONDS,
                nx=True,
            )
            return
        except Exception as exc:
            logger.warning("max_bot.webhook.dedupe.redis_fallback", extra={"error": str(exc)})

    now = time.time()
    _cleanup_dedupe_fallback(now)
    _webhook_dedupe_fallback[dedupe_key] = now


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
    request_secret: Optional[str],
    expected_secret: str,
) -> bool:
    """Verify the X-Max-Bot-Api-Secret header."""
    if not expected_secret:
        return True
    return request_secret == expected_secret


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
    x_max_bot_api_secret: Optional[str] = Header(None),
) -> JSONResponse:
    """Handle incoming webhook events from MAX Bot API."""
    settings = get_settings()
    webhook_secret = getattr(settings, "max_webhook_secret", "")

    if not _verify_secret(x_max_bot_api_secret, webhook_secret):
        logger.warning("max_bot.webhook.secret_reject")
        return JSONResponse({"error": "invalid_secret"}, status_code=403)

    raw_body = await request.body()
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    if await _is_duplicate_event(settings, raw_body, body):
        logger.info("max_bot.webhook.dedupe_hit")
        return JSONResponse({"ok": True, "duplicate": True})

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
        return JSONResponse({"error": "handler_failed"}, status_code=500)

    await _mark_event_processed(settings, raw_body, body)
    return JSONResponse({"ok": True})


async def _handle_bot_started(event: Dict[str, Any]) -> None:
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


async def _handle_message_created(event: Dict[str, Any]) -> None:
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


async def _handle_message_callback(event: Dict[str, Any]) -> None:
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


async def health_check() -> JSONResponse:
    """Health check endpoint with adapter/subscription visibility."""
    settings = get_settings()
    adapter = _get_max_adapter()
    adapter_ready = bool(getattr(adapter, "is_ready", False)) if adapter is not None else False
    return JSONResponse({
        "status": "ok",
        "service": "max_bot",
        "enabled": getattr(settings, "max_bot_enabled", False),
        "adapter_ready": adapter_ready,
        "webhook_url_configured": bool(getattr(settings, "max_webhook_url", "").strip()),
        "subscription_status": _subscription_status,
    })
