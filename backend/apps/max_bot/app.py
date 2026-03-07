"""VK Max bot application — FastAPI webhook server.

Receives webhook events from VK Max Bot API and processes them:
- bot_started: new user starts the bot → link max_user_id to candidate
- message_created: incoming text message → log to candidate chat
- message_callback: inline button press → handle action

Runs as a standalone FastAPI service (separate from admin_api and tg bot).

Max Bot API docs: https://dev.max.ru/docs-api
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from backend.core.settings import get_settings

logger = logging.getLogger(__name__)


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

    # Subscribe to Max webhook on startup
    if settings.max_bot_enabled and settings.max_bot_token:
        try:
            await _setup_webhook(settings)
        except Exception:
            logger.exception("max_bot: failed to set up webhook subscription")

    yield

    # Cleanup
    try:
        from backend.core.messenger.registry import get_registry
        from backend.core.messenger.protocol import MessengerPlatform

        adapter = get_registry().get(MessengerPlatform.MAX)
        if adapter:
            await adapter.close()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Create the Max bot FastAPI application."""
    app = FastAPI(
        title="RecruiterSmart Max Bot",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_api_route("/webhook", webhook_handler, methods=["POST"])
    app.add_api_route("/health", health_check, methods=["GET"])

    return app


async def _setup_webhook(settings) -> None:
    """Subscribe to Max webhook for receiving events.

    POST https://platform-api.max.ru/subscriptions
    Body: {"url": "...", "update_types": [...], "secret": "..."}
    """
    import httpx

    webhook_url = getattr(settings, "max_webhook_url", "").strip()
    if not webhook_url:
        logger.warning("max_bot: MAX_WEBHOOK_URL not set, skipping webhook setup")
        return

    webhook_secret = getattr(settings, "max_webhook_secret", "").strip()

    body: Dict[str, Any] = {
        "url": webhook_url,
        "update_types": [
            "bot_started",
            "message_created",
            "message_callback",
        ],
    }
    if webhook_secret:
        body["secret"] = webhook_secret

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        resp = await client.post(
            "https://platform-api.max.ru/subscriptions",
            json=body,
            headers={"Authorization": settings.max_bot_token},
        )
        if resp.status_code == 200:
            logger.info("max_bot: webhook subscription created", extra={"url": webhook_url})
        else:
            logger.error(
                "max_bot: webhook subscription failed",
                extra={"status": resp.status_code, "body": resp.text},
            )


def _verify_secret(
    request_secret: Optional[str],
    expected_secret: str,
) -> bool:
    """Verify the X-Max-Bot-Api-Secret header."""
    if not expected_secret:
        return True  # No secret configured → accept all
    return request_secret == expected_secret


async def webhook_handler(
    request: Request,
    x_max_bot_api_secret: Optional[str] = Header(None),
) -> JSONResponse:
    """Handle incoming webhook events from Max Bot API.

    Expected event structure:
    {
        "update_type": "message_created" | "bot_started" | "message_callback",
        "timestamp": 1234567890,
        "message": {...},  // for message_created
        "callback": {...}, // for message_callback
        "chat_id": 123,    // for bot_started
        "user": {...},     // for bot_started
        ...
    }
    """
    settings = get_settings()
    webhook_secret = getattr(settings, "max_webhook_secret", "")

    if not _verify_secret(x_max_bot_api_secret, webhook_secret):
        return JSONResponse({"error": "invalid_secret"}, status_code=403)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

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

    return JSONResponse({"ok": True})


async def _handle_bot_started(event: Dict[str, Any]) -> None:
    """Handle bot_started event — user opened the bot for the first time.

    This is the entry point for linking a Max user to a candidate in RS.
    We store the max_user_id and optionally set messenger_platform='max'.
    """
    user_info = event.get("user", {})
    chat_id = event.get("chat_id")
    max_user_id = user_info.get("user_id") or chat_id

    if not max_user_id:
        logger.warning("max_bot.bot_started: no user_id in event")
        return

    user_name = user_info.get("name", "")

    logger.info(
        "max_bot.bot_started",
        extra={"max_user_id": max_user_id, "user_name": user_name},
    )

    # Send welcome message
    try:
        from backend.core.messenger.registry import get_registry
        from backend.core.messenger.protocol import MessengerPlatform

        adapter = get_registry().get(MessengerPlatform.MAX)
        if adapter:
            await adapter.send_message(
                max_user_id,
                "Здравствуйте! Это бот компании для связи с кандидатами. "
                "Уведомления о статусе вашей заявки будут приходить сюда.",
            )
    except Exception:
        logger.exception("max_bot.bot_started: failed to send welcome")


async def _handle_message_created(event: Dict[str, Any]) -> None:
    """Handle incoming text message from a candidate via Max.

    Logs the message to the candidate's chat history so recruiters
    can see it in the admin UI.
    """
    message = event.get("message", {})
    body_data = message.get("body", {})
    text = body_data.get("text", "")
    sender = message.get("sender", {})
    max_user_id = sender.get("user_id")

    if not max_user_id or not text:
        return

    logger.info(
        "max_bot.message_created",
        extra={"max_user_id": max_user_id, "text_len": len(text)},
    )

    # Log to candidate chat (find candidate by max_user_id)
    try:
        from backend.core.db import async_session
        from backend.domain.candidates.models import User
        from sqlalchemy import select

        async with async_session() as session:
            candidate = await session.scalar(
                select(User).where(User.max_user_id == str(max_user_id))
            )
            if candidate:
                from backend.domain.candidates import services as candidate_services

                await candidate_services.log_inbound_chat_message(
                    candidate_tg_id=candidate.telegram_user_id or candidate.telegram_id or 0,
                    text=text,
                    payload={"source": "max", "max_user_id": str(max_user_id)},
                    author_label="candidate_max",
                )
            else:
                logger.debug(
                    "max_bot.message_created.no_candidate",
                    extra={"max_user_id": max_user_id},
                )
    except Exception:
        logger.exception(
            "max_bot.message_created.log_failed",
            extra={"max_user_id": max_user_id},
        )


async def _handle_message_callback(event: Dict[str, Any]) -> None:
    """Handle inline button press (callback) from Max.

    The callback payload matches the format used in Telegram callbacks
    (e.g., 'confirm_assignment:123') so we can reuse existing logic.
    """
    callback = event.get("callback", {})
    payload = callback.get("payload", "")
    user_info = callback.get("user", {})
    max_user_id = user_info.get("user_id")

    if not max_user_id or not payload:
        return

    logger.info(
        "max_bot.message_callback",
        extra={"max_user_id": max_user_id, "payload": payload},
    )

    # TODO: Route callback actions (confirm_assignment, reschedule, etc.)
    # For Phase 3, we log the callback. Full action routing will be added
    # when we connect Max callbacks to the same handlers as Telegram callbacks.

    try:
        from backend.core.messenger.registry import get_registry
        from backend.core.messenger.protocol import MessengerPlatform

        adapter = get_registry().get(MessengerPlatform.MAX)
        if adapter:
            await adapter.send_message(
                max_user_id,
                "Принято! Ваш запрос обрабатывается.",
            )
    except Exception:
        logger.exception("max_bot.message_callback: failed to respond")


async def health_check() -> JSONResponse:
    """Simple health check endpoint."""
    settings = get_settings()
    return JSONResponse({
        "status": "ok",
        "service": "max_bot",
        "enabled": getattr(settings, "max_bot_enabled", False),
    })
