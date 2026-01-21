"""Runtime integration helpers for bot state management."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional, Tuple

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramUnauthorizedError
from fastapi import FastAPI

from backend.apps.admin_ui.services.bot_service import (
    BOT_RUNTIME_AVAILABLE,
    BotService,
    IntegrationSwitch,
    configure_bot_service,
)
from backend.apps.bot.app import create_dispatcher
from backend.apps.bot.config import DEFAULT_BOT_PROPERTIES
from backend.apps.bot.reminders import (
    ReminderService,
    NullReminderService,
    configure_reminder_service,
    create_scheduler,
)
from backend.apps.bot.services import (
    NotificationService,
    StateManager,
    configure as configure_bot_services,
)
from backend.apps.bot.notifications.bootstrap import (
    configure_notification_service as bootstrap_notification_service,
    reset_notification_service as reset_bootstrap_notification_service,
)
from backend.apps.bot.state_store import build_state_manager
from backend.core.settings import get_settings
from backend.apps.bot.broker import InMemoryNotificationBroker, NotificationBroker
from backend.core.redis_factory import create_redis_client

try:  # pragma: no cover - redis is optional in some environments
    from redis.asyncio import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

NOTIFICATION_RETRY_BASE = 2.0
NOTIFICATION_RETRY_MAX = 60.0
NOTIFICATION_HEALTH_INTERVAL = 30.0


async def _create_notification_broker(redis_url: str) -> NotificationBroker:
    if Redis is None:
        raise RuntimeError("redis client library is not installed")
    client = create_redis_client(redis_url, component="broker")
    await client.ping()
    broker = NotificationBroker(client)
    await broker.start()
    return broker


async def _notification_health_watcher(
    app: FastAPI,
    integration: "BotIntegration",
    redis_url: str,
) -> None:
    if not redis_url:
        return
    backoff = NOTIFICATION_RETRY_BASE
    service = integration.notification_service
    while True:
        try:
            ping = await service.broker_ping()
        except Exception:
            ping = False

        if ping:
            app.state.notification_broker_status = "ok"
            app.state.notification_broker_available = True
            app.state.redis_available = True
            backoff = NOTIFICATION_RETRY_BASE
            await asyncio.sleep(NOTIFICATION_HEALTH_INTERVAL)
            continue

        try:
            broker = await _create_notification_broker(redis_url)
            await service.attach_broker(broker)
            integration.notification_broker = broker
            app.state.notification_broker_status = "ok"
            app.state.notification_broker_available = True
            app.state.redis_available = True
            backoff = NOTIFICATION_RETRY_BASE
            await asyncio.sleep(NOTIFICATION_HEALTH_INTERVAL)
            continue
        except Exception as exc:
            logger.warning("Notification broker reconnect attempt failed: %s", exc)
            app.state.notification_broker_status = "degraded"
            app.state.notification_broker_available = False
            try:
                await service.detach_broker()
            except Exception:
                pass
            integration.notification_broker = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, NOTIFICATION_RETRY_MAX)


async def _initialize_redis_broker_with_retry(redis_url: str, attempts: int = 3) -> Optional[NotificationBroker]:
    delay = NOTIFICATION_RETRY_BASE
    for attempt in range(1, attempts + 1):
        try:
            return await _create_notification_broker(redis_url)
        except Exception as exc:
            logger.warning(
                "Notification broker connection attempt %s/%s failed: %s",
                attempt,
                attempts,
                exc,
            )
            if attempt == attempts:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, NOTIFICATION_RETRY_MAX)
    return None


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
    bot_runner_task: Optional[asyncio.Task] = None
    bot_dispatcher: Optional[Dispatcher] = None
    bot_runner_stop: Optional[asyncio.Event] = None
    notification_watch_task: Optional[asyncio.Task] = None

    @classmethod
    def null_integration(cls) -> "BotIntegration":
        settings = get_settings()
        state_manager = build_state_manager(
            redis_url=None,
            ttl_seconds=getattr(settings, "state_ttl_seconds", 300),
        )
        reminder_service = NullReminderService()
        notification_service = bootstrap_notification_service(
            broker=None,
            scheduler=None,
        )
        bot_service = BotService(
            state_manager=state_manager,
            enabled=False,
            configured=False,
            integration_switch=IntegrationSwitch(initial=False),
            required=False,
        )
        configure_bot_service(bot_service)
        return cls(
            state_manager=state_manager,
            bot=None,
            bot_service=bot_service,
            integration_switch=IntegrationSwitch(initial=False),
            reminder_service=reminder_service,
            notification_service=notification_service,
            notification_broker=None,
        )

    async def shutdown(self) -> None:
        """Shutdown resources created for the integration."""

        if self.bot_runner_stop is not None:
            self.bot_runner_stop.set()
        if self.bot_runner_task is not None:
            self.bot_runner_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.bot_runner_task

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
        finally:
            reset_bootstrap_notification_service()
        if self.notification_watch_task is not None:
            self.notification_watch_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.notification_watch_task


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


def _should_autostart_bot(settings) -> bool:
    if settings.environment == "production":
        return False
    if not settings.bot_autostart:
        return False
    # Avoid double polling when uvicorn reload spawns multiple processes
    if os.getenv("UVICORN_RELOAD", "").lower() == "true":
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


async def _run_bot_polling(
    bot: Bot,
    dispatcher: Dispatcher,
    stop_event: asyncio.Event,
    integration_switch: Optional[IntegrationSwitch] = None,
) -> None:
    backoff_seconds = 3
    loop = asyncio.get_running_loop()
    registered_signals: list[int] = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
            registered_signals.append(sig)
        except (NotImplementedError, RuntimeError):
            continue
    while not stop_event.is_set():
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            me = await bot.get_me()
            logger.info(
                "Bot polling loop started",
                extra={"bot_id": me.id, "username": me.username},
            )
            await dispatcher.start_polling(bot)
            if stop_event.is_set():
                break
            logger.warning("Bot polling stopped unexpectedly; restarting in %s seconds", backoff_seconds)
            await asyncio.sleep(backoff_seconds)
        except asyncio.CancelledError:
            with suppress(Exception):
                await dispatcher.stop_polling()
            raise
        except TelegramUnauthorizedError:
            logger.error(
                "Bot polling disabled: Telegram rejected BOT_TOKEN. Update the token and restart.",
            )
            if integration_switch is not None:
                integration_switch.set(False)
            stop_event.set()
            break
        except Exception:
            logger.exception("Bot polling task crashed; retrying in %s seconds", backoff_seconds)
            await asyncio.sleep(backoff_seconds)
    with suppress(Exception):
        await dispatcher.stop_polling()
    for sig in registered_signals:
        with suppress((RuntimeError, ValueError)):
            loop.remove_signal_handler(sig)


async def setup_bot_state(app: FastAPI) -> BotIntegration:
    """Initialise the bot state manager for the admin application."""

    settings = get_settings()
    app.state.bot_enabled = settings.bot_enabled
    redis_url = getattr(settings, "redis_url", None) or ""
    broker_choice = (getattr(settings, "notification_broker", "memory") or "memory").strip().lower()
    # Allow degraded mode in production when Redis is missing - removed RuntimeError
    # if settings.environment == "production" and broker_choice == "redis" and not redis_url:
    #     raise RuntimeError("REDIS_URL is required in production when NOTIFICATION_BROKER=redis")

    force_memory = (
        settings.environment == "test"
        or not redis_url
        or broker_choice != "redis"
        or not settings.bot_enabled
    )
    state_manager = build_state_manager(
        redis_url=None if force_memory else redis_url,
        ttl_seconds=getattr(settings, "state_ttl_seconds", 604800),
    )
    bot, configured = _build_bot(settings)

    switch = IntegrationSwitch(initial=settings.bot_integration_enabled)
    if settings.environment == "test" and settings.database_url_sync.startswith("sqlite"):
        scheduler = None
    else:
        scheduler = create_scheduler(None if force_memory else redis_url) if settings.bot_enabled else None

    broker_instance: Optional[object] = None

    app.state.notification_broker_status = "disabled"
    app.state.notification_broker_available = False
    redis_required = settings.environment == "production" and broker_choice == "redis"
    if redis_required and not redis_url:
        app.state.notification_broker_status = "degraded"
        app.state.notification_broker_available = False

    if settings.bot_enabled and not force_memory and redis_url and Redis is not None and broker_choice != "memory":
        broker_instance = await _initialize_redis_broker_with_retry(redis_url)
        if broker_instance is not None:
            logger.info("Redis notification broker initialized (environment: %s)", settings.environment)
            app.state.notification_broker_status = "ok"
            app.state.notification_broker_available = True
            app.state.redis_available = True
        else:
            logger.error(
                "Redis notification broker could not be initialized; starting in degraded mode."
            )
            app.state.notification_broker_status = "degraded"
    elif not force_memory and redis_url and Redis is None:
        logger.error("Redis client library is missing; notification broker degraded.")
        app.state.notification_broker_status = "degraded"
        app.state.notification_broker_available = False
    elif not force_memory and not redis_url and settings.environment == "production":
        logger.warning("REDIS_URL is required in production; notification broker degraded.")
        app.state.notification_broker_status = "degraded"
        app.state.notification_broker_available = False

    if settings.bot_enabled and broker_instance is None:
        if settings.environment != "production" and (force_memory or broker_choice != "redis"):
            logger.warning(
                "Using InMemoryNotificationBroker (environment: %s). This is only suitable for development/testing.",
                settings.environment,
            )
            broker_instance = InMemoryNotificationBroker()
            await broker_instance.start()
            app.state.notification_broker_status = "memory"
            app.state.notification_broker_available = True
        else:
            logger.error(
                "Notification broker unavailable; service will remain degraded until Redis becomes reachable."
            )
            app.state.notification_broker_status = "degraded"
            app.state.notification_broker_available = False

    if settings.bot_enabled and scheduler is not None:
        reminder_service = ReminderService(scheduler=scheduler)
        configure_reminder_service(reminder_service)
        if not getattr(app.state, "db_available", True):
            logger.warning("Skipping reminder sync; database unavailable")
        else:
            await reminder_service.sync_jobs()
    else:
        reminder_service = NullReminderService()
    notification_service = bootstrap_notification_service(
        broker=broker_instance,
        scheduler=scheduler,
    )
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
    bot_runner_task: Optional[asyncio.Task] = None
    dispatcher: Optional[Dispatcher] = None
    bot_runner_stop: Optional[asyncio.Event] = None

    supervise_bot = (
        bot is not None
        and configured
        and _should_autostart_bot(settings)
    )

    if supervise_bot:
        dispatcher = create_dispatcher()
        configure_bot_services(bot, state_manager, dispatcher)
    else:
        configure_bot_services(bot if configured else None, state_manager)

    if settings.environment == "test" and settings.database_url_sync.startswith("sqlite"):
        logger.info("Notification service not started in test sqlite mode")
    elif settings.bot_enabled:
        # Start notification service (independent of bot supervision)
        # Use poll loop if scheduler is not available or in development
        allow_poll_loop = settings.environment != "production" or scheduler is None
        notification_service.start(allow_poll_loop=allow_poll_loop)
        logger.info(
            "Notification service started",
            extra={"allow_poll_loop": allow_poll_loop, "has_scheduler": scheduler is not None},
        )
    else:
        logger.info("Notification service not started; bot disabled")

    if supervise_bot and dispatcher is not None:
        bot_runner_stop = asyncio.Event()
        bot_runner_task = asyncio.create_task(
            _run_bot_polling(bot, dispatcher, bot_runner_stop, switch)
        )
        app.state.bot_dispatcher = dispatcher
        app.state.bot_runner_task = bot_runner_task
        app.state.bot_runner_stop = bot_runner_stop

    integration = BotIntegration(
        state_manager=state_manager,
        bot=bot,
        bot_service=bot_service,
        integration_switch=switch,
        reminder_service=reminder_service,
        notification_service=notification_service,
        notification_broker=broker_instance,
        bot_runner_task=bot_runner_task,
        bot_dispatcher=dispatcher,
        bot_runner_stop=bot_runner_stop,
        notification_watch_task=None,
    )

    if settings.bot_enabled and redis_url and Redis is not None:
        watch_task = asyncio.create_task(
            _notification_health_watcher(app, integration, redis_url)
        )
        integration.notification_watch_task = watch_task
        app.state.notification_watch_task = watch_task

    return integration


__all__ = ["BotIntegration", "setup_bot_state"]
