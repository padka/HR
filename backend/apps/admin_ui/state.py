"""Runtime integration helpers for bot state management."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from aiogram import Bot
from fastapi import FastAPI

from backend.apps.bot.config import DEFAULT_BOT_PROPERTIES
from backend.apps.bot.services import StateManager, configure as configure_bot_services
from backend.apps.admin_ui.services.bot_service import (
    BotService,
    configure_bot_service,
)
from backend.core.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class BotIntegration:
    """Holds runtime bot integration objects for cleanup."""

    state_manager: StateManager
    bot: Optional[Bot]
    bot_service: BotService

    async def shutdown(self) -> None:
        """Shutdown resources created for the integration."""

        if self.bot is not None:
            try:
                await self.bot.session.close()
            except Exception:  # pragma: no cover - network errors or aiohttp internals
                logger.exception("Failed to close bot session cleanly")


def setup_bot_state(app: FastAPI) -> BotIntegration:
    """Initialise the bot state manager for the admin application."""

    settings = get_settings()
    token = (settings.bot_token or "").strip()

    state_manager = StateManager()
    bot: Optional[Bot] = None

    if token and ":" in token:
        try:
            bot = Bot(token=token, default=DEFAULT_BOT_PROPERTIES)
        except Exception:  # pragma: no cover - network/environment specific
            logger.exception("Failed to initialise Telegram bot; Test 2 notifications disabled")
            bot = None
    else:
        logger.warning(
            "BOT_TOKEN is not configured or invalid; Test 2 notifications will not be sent."
        )

    configure_bot_services(bot, state_manager)

    bot_service = BotService(
        state_manager=state_manager,
        enabled=settings.enable_test2_bot,
        configured=bot is not None,
    )
    configure_bot_service(bot_service)

    app.state.bot = bot
    app.state.state_manager = state_manager
    app.state.bot_service = bot_service

    return BotIntegration(state_manager=state_manager, bot=bot, bot_service=bot_service)


__all__ = ["BotIntegration", "setup_bot_state"]

