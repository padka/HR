from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AIProviderError(RuntimeError):
    """Raised when an AI provider fails (network, auth, invalid response)."""


@dataclass(frozen=True)
class Usage:
    tokens_in: int = 0
    tokens_out: int = 0


class AIProvider(Protocol):
    name: str

    async def generate_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int,
        max_tokens: int,
    ) -> tuple[dict, Usage]:
        """Return parsed JSON payload and token usage.

        Implementations must not log prompts or raw outputs with PII.
        """

