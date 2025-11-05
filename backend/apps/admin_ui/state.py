"""Runtime integration helpers for bot state management."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from fastapi import FastAPI

from backend.apps.admin_ui.services.bot_service import (
    BOT_RUNTIME_AVAILABLE,
    BotService,
    IntegrationSwitch,
    configure_bot_service,
)
from backend.apps.bot.config import DEFAULT_BOT_PROPERTIES
from backend.apps.bot.reminders import (
    ReminderService,
    configure_reminder_service,
    create_scheduler,
)
from backend.apps.bot.services import (
    NotificationService,
    StateManager,
    configure as configure_bot_services,
    configure_notification_service,
)
from backend.apps.bot.state_store import build_state_manager
from backend.core.settings import get_settings
from backend.apps.bot.broker import InMemoryNotificationBroker, NotificationBroker

try:  # pragma: no cover - redis is optional in some environments
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass
class BotIntegration:
    """Holds runtime bot integration objects for cleanup."""

    state_manager: StateManager
    bot: Optional[Bot]
    bot_service: BotService
    integration_switch: IntegrationSwitch
    reminder_service: ReminderService
    notification_service: NotificationService
    notification_broker: Optional[object]

    async def shutdown(self) -> None:
        """Shutdown resources created for the integration."""

        if self.bot is not None:
            try:
                await self.bot.session.close()
            except Exception:  # pragma: no cover - network errors or aiohttp internals
                logger.exception("Failed to close bot session cleanly")

        try:
            await self.state_manager.close()
        except Exception:  # pragma: no cover - store cleanup issues
            logger.exception("Failed to close state manager cleanly")

        try:
            await self.reminder_service.shutdown()
        except Exception:  # pragma: no cover - scheduler cleanup issues
            logger.exception("Failed to shutdown reminder service cleanly")

        try:
            await self.notification_service.shutdown()
        except Exception:  # pragma: no cover - cleanup issues
            logger.exception("Failed to shutdown notification service cleanly")


def _build_bot(settings) -> Tuple[Optional[Bot], bool]:
    """Create bot runtime instance if configuration is valid."""

    if not settings.bot_enabled:
        logger.info(
            "Test 2 bot integration disabled via BOT_ENABLED flag; using NullBot."
        )
        return None, False

    if settings.bot_provider not in {"telegram", ""}:
        logger.warning(
            "Unsupported BOT_PROVIDER '%s'; expected 'telegram'.", settings.bot_provider
        )
        return None, False

    token = (settings.bot_token or "").strip()
    missing = []
    if not token:
        missing.append("BOT_TOKEN")
    if settings.bot_use_webhook and not settings.bot_webhook_url:
        missing.append("BOT_WEBHOOK_URL")

    if missing:
        message = "Bot enabled but missing: %s" % ", ".join(missing)
        if settings.bot_failfast:
            raise RuntimeError(message)
        logger.warning("%s; running with NullBot", message)
        return None, False

    session = None
    try:
        if settings.bot_api_base:
            api = TelegramAPIServer.from_base(settings.bot_api_base)
            session = AiohttpSession(api=api)
        bot = Bot(token=token, default=DEFAULT_BOT_PROPERTIES, session=session)
    except Exception:
        if session is not None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and not loop.is_closed():
                loop.create_task(session.close())
        logger.exception("Failed to initialise Telegram bot; running with NullBot")
        if settings.bot_failfast:
            raise
        return None, False

    return bot, True


async def setup_bot_state(app: FastAPI) -> BotIntegration:
    """Initialise the bot state manager for the admin application."""

    settings = get_settings()
    state_manager = build_state_manager(
        redis_url=getattr(settings, "redis_url", None),
        ttl_seconds=getattr(settings, "state_ttl_seconds", 604800),
    )
    bot, configured = _build_bot(settings)

    configure_bot_services(bot if configured else None, state_manager)

    switch = IntegrationSwitch(initial=settings.bot_integration_enabled)
    scheduler = create_scheduler(getattr(settings, "redis_url", None))

    redis_url = getattr(settings, "redis_url", None)
    broker_instance: Optional[object] = None

    # Production MUST use Redis - no in-memory fallback allowed
    if settings.environment == "production":
        if not redis_url:
            raise RuntimeError(
                "REDIS_URL is required in production environment. "
                "InMemory broker is not allowed in production. "
                "Please configure REDIS_URL environment variable."
            )
        if Redis is None:
            raise RuntimeError(
                "Redis client is not available. Install redis package: pip install redis"
            )

    if redis_url and Redis is not None:
        try:
            redis_client = Redis.from_url(redis_url)
            broker_instance = NotificationBroker(redis_client)
            await broker_instance.start()
            logger.info(f"Redis notification broker initialized (environment: {settings.environment})")
        except Exception as e:
            if settings.environment == "production":
                # In production, fail fast - don't fallback to in-memory
                raise RuntimeError(
                    f"Failed to initialize Redis notification broker in production: {e}"
                ) from e
            else:
                # In development/staging, allow fallback to in-memory
                logger.warning(
                    f"Failed to initialise Redis notification broker; using in-memory fallback. "
                    f"Error: {e}"
                )
                broker_instance = None

    if broker_instance is None:
        if settings.environment == "production":
            raise RuntimeError(
                "Cannot use in-memory notification broker in production. "
                "Redis is required for distributed worker coordination."
            )
        logger.warning(
            f"Using InMemoryNotificationBroker (environment: {settings.environment}). "
            "This is only suitable for development/testing."
        )
        broker_instance = InMemoryNotificationBroker()
        await broker_instance.start()

    reminder_service = ReminderService(scheduler=scheduler)
    configure_reminder_service(reminder_service)
    await reminder_service.sync_jobs()
    notification_service = NotificationService(
        scheduler=scheduler,
        broker=broker_instance,
        poll_interval=settings.notification_poll_interval,
        batch_size=settings.notification_batch_size,
        rate_limit_per_sec=settings.notification_rate_limit_per_sec,
        max_attempts=settings.notification_max_attempts,
        retry_base_delay=settings.notification_retry_base_seconds,
        retry_max_delay=settings.notification_retry_max_seconds,
    )
    configure_notification_service(notification_service)
    bot_service = BotService(
        state_manager=state_manager,
        enabled=settings.bot_enabled,
        configured=configured,
        integration_switch=switch,
        required=settings.test2_required,
    )
    configure_bot_service(bot_service)

    ready = bot_service.is_ready()
    if not ready:
        if not settings.bot_enabled:
            reason = "disabled"
        elif not BOT_RUNTIME_AVAILABLE:
            reason = "runtime_unavailable"
        elif not configured:
            reason = "not_configured"
        else:
            reason = "unknown"
    else:
        reason = None

    logger.info(
        "Bot integration initialised",
        extra={
            "provider": settings.bot_provider,
            "ready": ready,
            "mode": "real" if configured and ready else "null",
            "reason": reason,
        },
    )

    app.state.bot = bot
    app.state.state_manager = state_manager
    app.state.bot_service = bot_service
    app.state.bot_integration_switch = switch
    app.state.reminder_service = reminder_service
    app.state.notification_service = notification_service

    return BotIntegration(
        state_manager=state_manager,
        bot=bot,
        bot_service=bot_service,
        integration_switch=switch,
        reminder_service=reminder_service,
        notification_service=notification_service,
        notification_broker=broker_instance,
    )


__all__ = ["BotIntegration", "setup_bot_state"]
