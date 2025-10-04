"""Runtime integration helpers for bot state management."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from aiogram import Bot
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
from backend.apps.bot.services import StateManager
from backend.apps.bot.services import configure as configure_bot_services
from backend.apps.bot.state_store import build_state_manager
from backend.core.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class BotIntegration:
    """Holds runtime bot integration objects for cleanup."""

    state_manager: StateManager
    bot: Optional[Bot]
    bot_service: BotService
    integration_switch: IntegrationSwitch
    reminder_service: ReminderService

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

    try:
        bot = Bot(token=token, default=DEFAULT_BOT_PROPERTIES)
    except Exception:
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
    reminder_service = ReminderService(scheduler=scheduler)
    configure_reminder_service(reminder_service)
    await reminder_service.sync_jobs()
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

    return BotIntegration(
        state_manager=state_manager,
        bot=bot,
        bot_service=bot_service,
        integration_switch=switch,
        reminder_service=reminder_service,
    )


__all__ = ["BotIntegration", "setup_bot_state"]
