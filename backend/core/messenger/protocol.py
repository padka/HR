"""Messenger protocol — abstract interface for all messenger adapters."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class MessengerPlatform(str, enum.Enum):
    """Supported messaging platforms."""

    TELEGRAM = "telegram"
    MAX = "max"  # VK Max (ex-ICQ New)

    @classmethod
    def from_str(cls, value: str) -> "MessengerPlatform":
        """Parse platform from string, case-insensitive."""
        normalized = value.strip().lower()
        aliases = {
            "tg": cls.TELEGRAM,
            "telegram": cls.TELEGRAM,
            "max": cls.MAX,
            "vk_max": cls.MAX,
            "vkmax": cls.MAX,
            "icq": cls.MAX,
        }
        result = aliases.get(normalized)
        if result is None:
            raise ValueError(f"Unknown messenger platform: {value!r}")
        return result


@dataclass(frozen=True)
class InlineButton:
    """A button attached to a message (inline keyboard)."""

    text: str
    callback_data: Optional[str] = None
    url: Optional[str] = None
    kind: Optional[str] = None


@dataclass(frozen=True)
class SendResult:
    """Result of a send operation."""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = field(default=None, repr=False)


class MessengerProtocol:
    """Abstract protocol that every messenger adapter must implement.

    Adapters must be lightweight and stateless between calls.
    Heavy resources (HTTP sessions, bot instances) should be initialized
    once via ``configure()`` and shared across calls.
    """

    platform: MessengerPlatform

    async def configure(self, **kwargs: Any) -> None:
        """One-time initialization (set up HTTP clients, tokens, etc.).

        Called once during application startup. Idempotent.
        """
        raise NotImplementedError  # pragma: no cover

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        buttons: Optional[List[List[InlineButton]]] = None,
        parse_mode: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> SendResult:
        """Send a text message, optionally with inline buttons.

        Args:
            chat_id: Platform-specific user/chat identifier.
            text: Message body (may contain platform-specific markup).
            buttons: Optional grid of inline buttons (rows × cols).
            parse_mode: Optional hint ("HTML", "Markdown", etc.).
            correlation_id: Tracing ID for log correlation.

        Returns:
            SendResult indicating success or failure.
        """
        raise NotImplementedError  # pragma: no cover

    async def close(self) -> None:
        """Release resources (HTTP sessions, etc.)."""
        pass  # default: no-op

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} platform={getattr(self, 'platform', '?')}>"
