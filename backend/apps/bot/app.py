"""Application factory for the Telegram bot."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import suppress
from pathlib import Path
from typing import Tuple

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from backend.core.logging import configure_logging
from backend.core.settings import get_settings
from backend.core.content_updates import (
    ContentUpdateEvent,
    KIND_QUESTIONS_CHANGED,
    KIND_TEMPLATES_CHANGED,
    KIND_REMINDERS_CHANGED,
    run_content_updates_subscriber,
)

from .config import BOT_TOKEN, DEFAULT_BOT_PROPERTIES
from .handlers import register_routers
from .middleware import InboundChatLoggingMiddleware, TelegramIdentityMiddleware
from .services import (
    NotificationService,
    StateManager,
    configure as configure_services,
)
from .reminders import (
    ReminderService,
    configure_reminder_service,
    create_scheduler,
)
from .notifications.bootstrap import (
    configure_notification_service as bootstrap_notification_service,
    reset_notification_service as reset_bootstrap_notification_service,
)
from .state_store import build_state_manager, can_connect_redis

__all__ = ["create_application", "create_bot", "create_dispatcher", "main"]

configure_logging()


def _heartbeat_path() -> Path:
    settings = get_settings()
    configured = os.getenv("BOT_HEARTBEAT_FILE", "").strip()
    if configured:
        return Path(configured)
    return settings.data_dir / "bot_heartbeat"


def _write_heartbeat(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(f"{time.time():.6f}", encoding="utf-8")
    tmp_path.replace(path)


async def _heartbeat_loop(stop_event: asyncio.Event, path: Path) -> None:
    while not stop_event.is_set():
        try:
            _write_heartbeat(path)
        except Exception:
            logging.debug("bot.heartbeat_write_failed", exc_info=True)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            continue

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
    dispatcher.update.middleware(TelegramIdentityMiddleware())
    dispatcher.message.middleware(InboundChatLoggingMiddleware())
    register_routers(dispatcher)
    return dispatcher


async def create_application(
    token: str | None = None,
) -> Tuple[Bot, Dispatcher, StateManager, ReminderService, NotificationService]:
    """Create and configure the bot application components."""
    bot = create_bot(token)
    dispatcher = create_dispatcher()
    settings = get_settings()
    redis_url = getattr(settings, "redis_url", None)
    redis_state_ok = await can_connect_redis(redis_url, component="state_store")
    state_manager = build_state_manager(
        redis_url=redis_url if redis_state_ok else None,
        ttl_seconds=getattr(settings, "state_ttl_seconds", 604800),
    )
    scheduler = create_scheduler(redis_url if redis_state_ok else None)
    reminder_service = ReminderService(scheduler=scheduler)
    configure_reminder_service(reminder_service)
    await reminder_service.sync_jobs()
    notification_service = bootstrap_notification_service(
        broker=None,
        scheduler=scheduler,
    )
    configure_services(bot, state_manager, dispatcher)
    return bot, dispatcher, state_manager, reminder_service, notification_service


async def main() -> None:
    settings = get_settings()
    heartbeat_file = _heartbeat_path()
    heartbeat_stop = asyncio.Event()
    heartbeat_task: asyncio.Task | None = None
    content_updates_stop = asyncio.Event()
    content_updates_task: asyncio.Task | None = None
    bot: Bot | None = None
    reminder_service: ReminderService | None = None
    notification_service: NotificationService | None = None

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

    try:
        bot, dispatcher, _, reminder_service, notification_service = await create_application()
        # Start notification service to process outbox queue
        notification_service.start()
        logging.info("✓ Notification service started")

        async def _handle_content_update(event: ContentUpdateEvent) -> None:
            if event.kind == KIND_QUESTIONS_CHANGED:
                # refresh_questions_bank uses sync SQLAlchemy session; run it off the event loop.
                from backend.apps.bot.config import refresh_questions_bank

                await asyncio.to_thread(refresh_questions_bank)
                logging.info("Content update applied: questions refreshed")
                return

            if event.kind == KIND_TEMPLATES_CHANGED:
                payload = dict(event.payload or {})
                key = payload.get("key")
                locale = payload.get("locale") or "ru"
                channel = payload.get("channel") or "tg"
                city_id = payload.get("city_id")
                try:
                    city_id_value = int(city_id) if city_id is not None else None
                except (TypeError, ValueError):
                    city_id_value = None
                if notification_service is not None:
                    await notification_service.invalidate_template_cache(
                        key=str(key) if key else None,
                        locale=str(locale or "ru"),
                        channel=str(channel or "tg"),
                        city_id=city_id_value,
                    )
                try:
                    # Clear template proxy cache too (it uses a global provider).
                    from backend.apps.bot.services import templates

                    templates.clear_cache()
                except Exception:
                    pass
                logging.info("Content update applied: templates invalidated")
                return

            if event.kind == KIND_REMINDERS_CHANGED:
                if reminder_service is None:
                    return
                try:
                    await reminder_service.reschedule_active_slots()
                    logging.info("Content update applied: reminders rescheduled")
                except Exception as exc:
                    logging.warning("Content update failed: reminders reschedule error=%s", exc)
                return

        async def _content_updates_supervisor(redis_url: str) -> None:
            backoff = 1.0
            while not content_updates_stop.is_set():
                try:
                    await run_content_updates_subscriber(
                        redis_url=redis_url,
                        stop_event=content_updates_stop,
                        on_event=_handle_content_update,
                    )
                    return
                except Exception as exc:
                    if content_updates_stop.is_set():
                        return
                    logging.warning("content_updates subscriber crashed: %s", exc)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)

        if settings.redis_url:
            content_updates_task = asyncio.create_task(_content_updates_supervisor(settings.redis_url))

        await bot.delete_webhook(drop_pending_updates=True)
        me = await bot.get_me()
        logging.warning("BOOT: using bot id=%s, username=@%s", me.id, me.username)
        _write_heartbeat(heartbeat_file)
        heartbeat_task = asyncio.create_task(_heartbeat_loop(heartbeat_stop, heartbeat_file))
        # NOTE: Database migrations should be run separately before starting the bot
        # Run: python scripts/run_migrations.py
        await dispatcher.start_polling(bot)
    finally:
        heartbeat_stop.set()
        content_updates_stop.set()
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
        if content_updates_task is not None:
            content_updates_task.cancel()
            with suppress(asyncio.CancelledError):
                await content_updates_task
        with suppress(FileNotFoundError):
            heartbeat_file.unlink()
        if reminder_service is not None:
            await reminder_service.shutdown()
        if notification_service is not None:
            await notification_service.shutdown()
        reset_bootstrap_notification_service()
        if bot is not None:
            with suppress(Exception):
                await bot.session.close()
        # Disconnect cache
        try:
            if redis_url:
                from backend.core.cache import disconnect_cache
                await disconnect_cache()
        except Exception:
            logging.debug("bot.cache_disconnect_error", exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
