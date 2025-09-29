"""Bot client integration helpers for launching Test 2."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from fastapi import Request

try:  # pragma: no cover - optional dependency handling
    from backend.apps.bot.config import DEFAULT_TZ, TEST1_QUESTIONS, State as BotState
    from backend.apps.bot.services import StateManager, start_test2
    BOT_RUNTIME_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when bot package is unavailable
    DEFAULT_TZ = "Europe/Moscow"
    TEST1_QUESTIONS: list[str] = []
    BOT_RUNTIME_AVAILABLE = False

    class _DummyStateManager:  # type: ignore[too-few-public-methods]
        """Fallback state manager used when bot runtime is unavailable."""

        def get(self, *_args, **_kwargs):  # pragma: no cover - runtime safety net
            return {}

        def set(self, *_args, **_kwargs) -> None:  # pragma: no cover - runtime safety net
            return None

        def ensure(self, *_args, **_kwargs):  # pragma: no cover - runtime safety net
            return {}

    StateManager = _DummyStateManager  # type: ignore[assignment]

    async def start_test2(user_id: int) -> None:  # pragma: no cover - runtime safety net
        raise RuntimeError("Bot runtime is unavailable")

    BotState = dict  # type: ignore[assignment]


logger = logging.getLogger(__name__)


@dataclass
class BotSendResult:
    """Represents the outcome of attempting to launch Test 2."""

    ok: bool
    dispatched: bool
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BotService:
    """High level bot client responsible for launching Test 2."""

    state_manager: StateManager
    enabled: bool
    configured: bool

    skip_message: str = "Отправка Теста 2 отключена в текущем окружении."

    @property
    def health_status(self) -> str:
        """Return health status token for diagnostics."""

        if not self.enabled:
            return "disabled"
        if not BOT_RUNTIME_AVAILABLE:
            return "unavailable"
        if not self.configured:
            return "unconfigured"
        return "ok"

    def with_configuration(self, configured: bool) -> "BotService":
        """Return a copy of the service with updated configuration flag."""

        return BotService(
            state_manager=self.state_manager,
            enabled=self.enabled,
            configured=configured,
            skip_message=self.skip_message,
        )

    async def send_test2(
        self,
        candidate_id: int,
        candidate_tz: Optional[str],
        candidate_city: Optional[int],
        candidate_name: str,
    ) -> BotSendResult:
        """Launch Test 2 for a candidate."""

        if not self.enabled:
            logger.info("Test 2 bot integration disabled via feature flag; skipping launch.")
            return BotSendResult(ok=True, dispatched=False, message=self.skip_message)

        if not BOT_RUNTIME_AVAILABLE or not self.configured:
            logger.warning(
                "Bot integration is enabled but not configured; cannot send Test 2.",
            )
            return BotSendResult(
                ok=False,
                dispatched=False,
                error="Бот недоступен. Проверьте его конфигурацию.",
            )

        previous_state: Dict[str, object] = self.state_manager.get(candidate_id) or {}

        sequence = previous_state.get("t1_sequence")
        if sequence:
            try:
                sequence = list(sequence)
            except TypeError:
                sequence = list(TEST1_QUESTIONS)
        else:
            sequence = list(TEST1_QUESTIONS)

        new_state: BotState = BotState(
            flow="intro",
            t1_idx=None,
            t1_current_idx=None,
            test1_answers=previous_state.get("test1_answers", {}),
            t1_last_prompt_id=None,
            t1_last_question_text="",
            t1_requires_free_text=False,
            t1_sequence=sequence,
            fio=previous_state.get("fio", candidate_name or ""),
            city_name=previous_state.get("city_name", ""),
            city_id=previous_state.get("city_id", candidate_city),
            candidate_tz=candidate_tz or previous_state.get("candidate_tz", DEFAULT_TZ),
            t2_attempts={},
            picked_recruiter_id=None,
            picked_slot_id=None,
        )

        self.state_manager.set(candidate_id, new_state)

        try:
            await start_test2(candidate_id)
        except Exception as exc:  # pragma: no cover - network/environment errors
            logger.exception("Failed to start Test 2 for candidate %s", candidate_id)
            if isinstance(exc, RuntimeError) and "bot" in str(exc).lower():
                return BotSendResult(
                    ok=False,
                    dispatched=False,
                    error="Бот недоступен. Проверьте его конфигурацию.",
                )
            return BotSendResult(ok=False, dispatched=False, error=str(exc))

        return BotSendResult(ok=True, dispatched=True)


_bot_service: Optional[BotService] = None


def configure_bot_service(service: BotService) -> None:
    """Register the bot service as a global singleton for background usage."""

    global _bot_service
    _bot_service = service


def get_bot_service() -> BotService:
    """Return the globally configured bot service."""

    if _bot_service is None:
        raise RuntimeError("Bot service is not configured")
    return _bot_service


def provide_bot_service(request: Request) -> BotService:
    """FastAPI dependency provider for the bot service."""

    service = getattr(request.app.state, "bot_service", None)
    if service is not None:
        return service
    return get_bot_service()


__all__ = [
    "BotSendResult",
    "BotService",
    "configure_bot_service",
    "get_bot_service",
    "provide_bot_service",
]
