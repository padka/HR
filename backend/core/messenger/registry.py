"""Messenger adapter registry — singleton lookup for platform adapters."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.core.messenger.protocol import MessengerPlatform, MessengerProtocol

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

__all__ = [
    "MessengerRegistry",
    "get_registry",
    "get_adapter",
    "register_adapter",
    "resolve_adapter_for_candidate",
]


class MessengerRegistry:
    """Thread-safe registry of messenger adapters keyed by platform."""

    def __init__(self) -> None:
        self._adapters: dict[MessengerPlatform, MessengerProtocol] = {}

    def register(self, adapter: MessengerProtocol) -> None:
        """Register an adapter for its platform."""
        platform = adapter.platform
        if platform in self._adapters:
            logger.warning(
                "messenger.registry.overwrite",
                extra={"platform": platform.value},
            )
        self._adapters[platform] = adapter
        logger.info(
            "messenger.registry.registered",
            extra={"platform": platform.value, "adapter": adapter.__class__.__name__},
        )

    def get(self, platform: MessengerPlatform) -> MessengerProtocol | None:
        """Return adapter for the given platform, or None."""
        return self._adapters.get(platform)

    def get_or_raise(self, platform: MessengerPlatform) -> MessengerProtocol:
        """Return adapter or raise RuntimeError."""
        adapter = self.get(platform)
        if adapter is None:
            raise RuntimeError(
                f"No messenger adapter registered for platform {platform.value!r}. "
                f"Available: {[p.value for p in self._adapters]}"
            )
        return adapter

    def unregister(self, platform: MessengerPlatform) -> MessengerProtocol | None:
        """Remove and return an adapter for the given platform if present."""
        return self._adapters.pop(platform, None)

    @property
    def platforms(self) -> list[MessengerPlatform]:
        """Return list of registered platforms."""
        return list(self._adapters.keys())

    def __contains__(self, platform: MessengerPlatform) -> bool:
        return platform in self._adapters

    def __repr__(self) -> str:  # pragma: no cover
        platforms = ", ".join(p.value for p in self._adapters)
        return f"<MessengerRegistry [{platforms}]>"


# ── Module-level singleton ──────────────────────────────────────────────

_registry: MessengerRegistry | None = None


def get_registry() -> MessengerRegistry:
    """Return (or lazily create) the global messenger registry."""
    global _registry
    if _registry is None:
        _registry = MessengerRegistry()
    return _registry


def register_adapter(adapter: MessengerProtocol) -> None:
    """Convenience: register adapter into the global registry."""
    get_registry().register(adapter)


def get_adapter(platform: MessengerPlatform) -> MessengerProtocol:
    """Convenience: fetch adapter from the global registry (raises if missing)."""
    return get_registry().get_or_raise(platform)


def unregister_adapter(platform: MessengerPlatform) -> MessengerProtocol | None:
    """Convenience: remove an adapter from the global registry."""
    return get_registry().unregister(platform)


def resolve_adapter_for_candidate(
    *,
    messenger_platform: str | None = None,
    telegram_user_id: int | None = None,
    max_user_id: int | str | None = None,
) -> tuple[MessengerProtocol, int | str]:
    """Pick the right adapter + chat_id for a candidate.

    Resolution order:
    1. If ``messenger_platform`` is explicitly set, use that.
    2. Fall back to MAX if ``max_user_id`` is present and adapter exists.
    3. Fall back to Telegram if ``telegram_user_id`` is present.
    3. Raise ValueError if no viable channel.

    Returns:
        (adapter, chat_id) tuple.
    """
    registry = get_registry()

    # 1) Explicit preference
    if messenger_platform:
        platform = MessengerPlatform.from_str(messenger_platform)
        adapter = registry.get(platform)
        if adapter is not None:
            if platform == MessengerPlatform.MAX and max_user_id:
                return adapter, max_user_id
            if platform == MessengerPlatform.TELEGRAM and telegram_user_id:
                return adapter, telegram_user_id

    # 2) Prefer MAX when a MAX identity exists and adapter is registered.
    if max_user_id:
        max_adapter = registry.get(MessengerPlatform.MAX)
        if max_adapter is not None:
            return max_adapter, max_user_id

    # 3) Fallback to Telegram
    if telegram_user_id:
        tg_adapter = registry.get(MessengerPlatform.TELEGRAM)
        if tg_adapter is not None:
            return tg_adapter, telegram_user_id

    raise ValueError(
        "Cannot resolve messenger adapter: candidate has no registered MAX or Telegram channel "
        "or no matching adapters are registered."
    )
