"""Application factory for the Telegram bot."""

from __future__ import annotations

import asyncio
import logging
from typing import Tuple

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from backend.core.settings import get_settings

from .config import BOT_TOKEN, DEFAULT_BOT_PROPERTIES
from .handlers import register_routers
from .services import (
    NotificationService,
    StateManager,
    configure as configure_services,
    configure_notification_service,
)
from .reminders import (
    ReminderService,
    configure_reminder_service,
    create_scheduler,
)
from .state_store import build_state_manager

__all__ = ["create_application", "create_bot", "create_dispatcher", "main"]


def create_bot(token: str | None = None) -> Bot:
    actual_token = token or BOT_TOKEN
    if not actual_token or ":" not in actual_token:
        raise RuntimeError(
            "BOT_TOKEN не найден или некорректен. Задай BOT_TOKEN=... (или используй .env)"
        )
    session = None
    settings = get_settings()
    try:
        if settings.bot_api_base:
            api = TelegramAPIServer.from_base(settings.bot_api_base)
            session = AiohttpSession(api=api)
        return Bot(token=actual_token, default=DEFAULT_BOT_PROPERTIES, session=session)
    except Exception:
        if session is not None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and not loop.is_closed():
                loop.create_task(session.close())
        raise


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    register_routers(dispatcher)
    return dispatcher


async def create_application(
    token: str | None = None,
) -> Tuple[Bot, Dispatcher, StateManager, ReminderService, NotificationService]:
    """Create and configure the bot application components."""
    bot = create_bot(token)
    dispatcher = create_dispatcher()
    settings = get_settings()
    state_manager = build_state_manager(
        redis_url=getattr(settings, "redis_url", None),
        ttl_seconds=getattr(settings, "state_ttl_seconds", 604800),
    )
    scheduler = create_scheduler(getattr(settings, "redis_url", None))
    reminder_service = ReminderService(scheduler=scheduler)
    configure_reminder_service(reminder_service)
    await reminder_service.sync_jobs()
    notification_service = NotificationService(
        scheduler=scheduler,
        poll_interval=settings.notification_poll_interval,
        batch_size=settings.notification_batch_size,
        rate_limit_per_sec=settings.notification_rate_limit_per_sec,
        max_attempts=settings.notification_max_attempts,
        retry_base_delay=settings.notification_retry_base_seconds,
        retry_max_delay=settings.notification_retry_max_seconds,
    )
    configure_notification_service(notification_service)
    configure_services(bot, state_manager, dispatcher)
    return bot, dispatcher, state_manager, reminder_service, notification_service


async def main() -> None:
    settings = get_settings()

    # Initialize Phase 2 Performance Cache
    redis_url = settings.redis_url
    if redis_url:
        try:
            from urllib.parse import urlparse
            from backend.core.cache import CacheConfig, init_cache, connect_cache, disconnect_cache

            parsed = urlparse(redis_url)
            cache_config = CacheConfig(
                host=parsed.hostname or "localhost",
                port=parsed.port or 6379,
                db=int(parsed.path.strip("/") or "0") if parsed.path else 0,
                password=parsed.password,
            )
            init_cache(cache_config)
            await connect_cache()
            logging.info(f"✓ Phase 2 Cache initialized: {parsed.hostname}:{parsed.port}")
        except Exception as e:
            if settings.environment == "production":
                raise RuntimeError(f"Failed to initialize cache in production: {e}") from e
            else:
                logging.warning(f"Cache initialization failed (non-production): {e}")
    else:
        logging.info("Cache disabled (no REDIS_URL)")

    bot, dispatcher, _, reminder_service, notification_service = await create_application()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        me = await bot.get_me()
        logging.warning("BOOT: using bot id=%s, username=@%s", me.id, me.username)
        # NOTE: Database migrations should be run separately before starting the bot
        # Run: python scripts/run_migrations.py
        await dispatcher.start_polling(bot)
    finally:
        await reminder_service.shutdown()
        await notification_service.shutdown()
        # Disconnect cache
        try:
            if redis_url:
                from backend.core.cache import disconnect_cache
                await disconnect_cache()
        except Exception:
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
