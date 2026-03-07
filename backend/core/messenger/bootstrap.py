"""Bootstrap messenger adapters at application startup."""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.core.messenger.protocol import MessengerPlatform
from backend.core.messenger.registry import get_registry

logger = logging.getLogger(__name__)


async def bootstrap_messenger_adapters(
    *,
    bot: Optional[Any] = None,
    max_bot_enabled: bool = False,
    max_bot_token: str = "",
) -> None:
    """Register all configured messenger adapters.

    Call this once during application startup (e.g. in ``create_application()``).

    Args:
        bot: Existing aiogram Bot instance (or None for lazy resolution).
        max_bot_enabled: Whether VK Max adapter should be initialized.
        max_bot_token: Bot token for VK Max API.
    """
    registry = get_registry()

    # 1. Telegram adapter (always registered when bot subsystem is present)
    try:
        from backend.core.messenger.telegram_adapter import TelegramAdapter

        tg = TelegramAdapter()
        await tg.configure(bot=bot)
        registry.register(tg)
    except Exception:
        logger.exception("messenger.bootstrap.telegram_failed")

    # 2. VK Max adapter (optional)
    if max_bot_enabled and max_bot_token:
        try:
            from backend.core.messenger.max_adapter import MaxAdapter

            mx = MaxAdapter()
            await mx.configure(token=max_bot_token)
            registry.register(mx)
        except Exception:
            logger.exception("messenger.bootstrap.max_failed")
    elif max_bot_enabled:
        logger.warning(
            "messenger.bootstrap.max_skipped",
            extra={"reason": "MAX_BOT_TOKEN is empty"},
        )

    logger.info(
        "messenger.bootstrap.done",
        extra={"platforms": [p.value for p in registry.platforms]},
    )
