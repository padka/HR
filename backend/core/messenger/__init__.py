"""Messenger abstraction layer.

Provides a platform-agnostic interface for sending messages to candidates
and recruiters via different messaging platforms (Telegram, VK Max, etc.).
"""

from backend.core.messenger.protocol import (
    MessengerPlatform,
    MessengerProtocol,
    SendResult,
)
from backend.core.messenger.registry import (
    get_adapter,
    get_registry,
    register_adapter,
    resolve_adapter_for_candidate,
)

__all__ = [
    "MessengerPlatform",
    "MessengerProtocol",
    "SendResult",
    "get_adapter",
    "get_registry",
    "register_adapter",
    "resolve_adapter_for_candidate",
]
