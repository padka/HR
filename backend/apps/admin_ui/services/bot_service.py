"""Bot client integration helpers for launching Test 2."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Dict, Optional

from fastapi import Request
from backend.domain.repositories import get_city

try:  # pragma: no cover - optional dependency handling
    from aiohttp import ClientError as _AioHttpClientError
except Exception:  # pragma: no cover - optional dependency
    _AioHttpClientError = Exception  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency handling
    from backend.apps.bot import templates as bot_templates, services
    from backend.apps.bot.config import DEFAULT_TZ, TEST1_QUESTIONS
    from backend.apps.bot.config import State as BotState
    from backend.apps.bot.services import StateManager, get_bot, start_test2
    from backend.apps.bot.events import InterviewSuccessEvent

    BOT_RUNTIME_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when bot package is unavailable
    DEFAULT_TZ = "Europe/Moscow"
    TEST1_QUESTIONS: list[str] = []
    BOT_RUNTIME_AVAILABLE = False

    class _DummyStateManager:  # type: ignore[too-few-public-methods]
        """Fallback state manager used when bot runtime is unavailable."""

        async def get(self, *_args, **_kwargs):  # pragma: no cover - runtime safety net
            return {}

        async def set(
            self, *_args, **_kwargs
        ) -> None:  # pragma: no cover - runtime safety net
            return None

        async def update(
            self, *_args, **_kwargs
        ):  # pragma: no cover - runtime safety net
            return {}

        async def atomic_update(
            self, *_args, **_kwargs
        ):  # pragma: no cover - runtime safety net
            return None

    StateManager = _DummyStateManager  # type: ignore[assignment]

    async def start_test2(
        user_id: int,
    ) -> None:  # pragma: no cover - runtime safety net
        raise RuntimeError("Bot runtime is unavailable")

    BotState = dict  # type: ignore[assignment]

    async def _dummy_tpl(
        *_args, **_kwargs
    ) -> str:  # pragma: no cover - runtime safety net
        return ""

    bot_templates = SimpleNamespace(tpl=_dummy_tpl)

    def get_bot():  # type: ignore[override]
        raise RuntimeError("Bot runtime is unavailable")

    async def _dummy_async(*_args, **_kwargs):  # pragma: no cover - runtime safety net
        return None

    services = SimpleNamespace(
        set_pending_test2=_dummy_async,
        dispatch_interview_success=_dummy_async,
    )

    @dataclass
    class InterviewSuccessEvent:  # pragma: no cover - runtime safety net
        candidate_id: int
        candidate_name: str
        candidate_tz: str
        city_id: Optional[int]
        city_name: Optional[str]
        slot_id: Optional[int] = None
        required: bool = False


logger = logging.getLogger(__name__)


class IntegrationSwitch:
    """Runtime toggle over the bot integration."""

    def __init__(self, *, initial: bool) -> None:
        self._enabled = bool(initial)
        self._updated_at = datetime.now(timezone.utc)

    def is_enabled(self) -> bool:
        return self._enabled

    def set(self, value: bool) -> None:
        self._enabled = bool(value)
        self._updated_at = datetime.now(timezone.utc)

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    def snapshot(self) -> Dict[str, object]:
        return {
            "enabled": self._enabled,
            "updated_at": self._updated_at,
        }


@dataclass
class BotSendResult:
    """Represents the outcome of attempting to launch Test 2."""

    ok: bool
    status: str
    message: Optional[str] = None
    error: Optional[str] = None
    telegram_message_id: Optional[int] = None


@dataclass
class BotService:
    """High level bot client responsible for launching Test 2."""

    state_manager: StateManager
    enabled: bool
    configured: bool
    integration_switch: IntegrationSwitch

    required: bool
    skip_message: str = "Отправка Теста 2 отключена в текущем окружении."
    not_configured_message: str = "Отправка Теста 2 пропущена: бот не настроен."
    transient_message: str = "Бот временно недоступен. Попробуйте позже."
    failure_message: str = "Не удалось отправить Тест 2 кандидату."
    rejection_failure_message: str = "Не удалось отправить отказ кандидату."

    def is_ready(self) -> bool:
        """Return whether the bot can be used for Test 2 dispatches."""

        return (
            self.enabled
            and self.integration_switch.is_enabled()
            and BOT_RUNTIME_AVAILABLE
            and self.configured
        )

    @property
    def health_status(self) -> str:
        """Return health status token for diagnostics."""

        if not self.enabled:
            return "disabled"
        if not self.integration_switch.is_enabled():
            return "disabled_runtime"
        if not BOT_RUNTIME_AVAILABLE:
            return "unavailable"
        if not self.configured:
            return "unconfigured"
        return "ready"

    def with_configuration(self, configured: bool) -> "BotService":
        """Return a copy of the service with updated configuration flag."""

        return BotService(
            state_manager=self.state_manager,
            enabled=self.enabled,
            configured=configured,
            integration_switch=self.integration_switch,
            required=self.required,
            skip_message=self.skip_message,
            not_configured_message=self.not_configured_message,
            transient_message=self.transient_message,
            failure_message=self.failure_message,
            rejection_failure_message=self.rejection_failure_message,
        )

    async def send_test2(
        self,
        candidate_id: int,
        candidate_tz: Optional[str],
        candidate_city: Optional[int],
        candidate_name: str,
        *,
        required: Optional[bool] = None,
        slot_id: Optional[int] = None,
    ) -> BotSendResult:
        """Launch Test 2 for a candidate."""

        if not self.integration_switch.is_enabled():
            logger.info("Bot integration switch is disabled; skipping Test 2 launch.")
            return BotSendResult(
                ok=True,
                status="skipped:disabled",
                message=self.skip_message,
            )

        must_succeed = self.required if required is None else required

        if not self.enabled:
            logger.info(
                "Test 2 bot integration disabled via feature flag; skipping launch."
            )
            return BotSendResult(
                ok=True,
                status="skipped:not_configured",
                message=self.skip_message,
            )

        if not BOT_RUNTIME_AVAILABLE or not self.configured:
            logger.warning(
                "Bot integration is enabled but not configured; cannot send Test 2.",
            )
            if must_succeed:
                return BotSendResult(
                    ok=False,
                    status="skipped:not_configured",
                    error="Бот недоступен. Проверьте его конфигурацию.",
                )
            return BotSendResult(
                ok=True,
                status="skipped:not_configured",
                message=self.not_configured_message,
            )

        previous_state: Dict[str, object] = (
            await self.state_manager.get(candidate_id) or {}
        )

        candidate_tz_value = (
            candidate_tz or previous_state.get("candidate_tz") or DEFAULT_TZ
        )
        city_id_value = previous_state.get("city_id", candidate_city)
        city_name_value = previous_state.get("city_name")

        if not city_name_value and city_id_value is not None:
            try:
                city = await get_city(int(city_id_value))
            except Exception:
                city = None
            if city is not None:
                city_name_value = getattr(city, "name_plain", None) or getattr(city, "name", "")

        candidate_name_value = previous_state.get("fio", candidate_name or "") or ""

        await services.set_pending_test2(
            candidate_id,
            {
                "candidate_tz": candidate_tz_value,
                "candidate_city_id": city_id_value,
                "candidate_name": candidate_name_value,
                "slot_id": slot_id,
                "required": must_succeed,
            },
        )

        event = InterviewSuccessEvent(
            candidate_id=candidate_id,
            candidate_name=candidate_name_value or "Кандидат",
            candidate_tz=candidate_tz_value or DEFAULT_TZ,
            city_id=city_id_value,
            city_name=city_name_value,
            slot_id=slot_id,
            required=must_succeed,
        )

        try:
            await services.dispatch_interview_success(event)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to dispatch interview success event")
            if must_succeed:
                return BotSendResult(
                    ok=False,
                    status="skipped:error",
                    error=self.failure_message,
                )
            return BotSendResult(
                ok=True,
                status="skipped:error",
                message=self.failure_message,
            )

        return BotSendResult(ok=True, status="sent_test2")

    async def send_rejection(
        self,
        candidate_id: int,
        *,
        city_id: Optional[int],
        template_key: str,
        context: Dict[str, object],
    ) -> BotSendResult:
        if not self.enabled:
            logger.info("Bot integration disabled; skipping rejection message.")
            return BotSendResult(
                ok=True,
                status="skipped:disabled",
                message=self.skip_message,
            )

        if not self.integration_switch.is_enabled():
            logger.info("Bot integration switch disabled; skipping rejection message.")
            return BotSendResult(
                ok=True,
                status="skipped:disabled",
                message=self.skip_message,
            )

        if not BOT_RUNTIME_AVAILABLE or not self.configured:
            logger.warning(
                "Bot integration is not configured; cannot send rejection message."
            )
            return BotSendResult(
                ok=False,
                status="skipped:not_configured",
                error=self.rejection_failure_message,
            )

        try:
            bot = get_bot()
        except Exception:  # pragma: no cover - runtime safety net
            logger.exception(
                "Bot runtime is unavailable; cannot send rejection message."
            )
            return BotSendResult(
                ok=False,
                status="skipped:not_configured",
                error=self.rejection_failure_message,
            )

        text = await bot_templates.tpl(city_id, template_key, **context)
        if not text.strip():
            logger.warning("Rejection template '%s' produced empty text", template_key)
            return BotSendResult(
                ok=False,
                status="skipped:error",
                error=self.rejection_failure_message,
            )

        try:
            await bot.send_message(candidate_id, text)
        except Exception as exc:  # pragma: no cover - network/environment errors
            if _is_transient_error(exc):
                logger.exception("Transient error while sending rejection message")
                return BotSendResult(
                    ok=False,
                    status="queued_retry",
                    error=self.transient_message,
                )

            logger.exception(
                "Failed to send rejection message to candidate %s", candidate_id
            )
            return BotSendResult(
                ok=False,
                status="skipped:error",
                error=self.rejection_failure_message,
            )

        return BotSendResult(ok=True, status="sent_rejection")

    async def send_chat_message(
        self,
        telegram_id: int,
        text: str,
        *,
        reply_markup: Optional[object] = None,
    ) -> BotSendResult:
        """Send a plain text message to candidate via bot."""

        if not self.integration_switch.is_enabled() or not self.enabled:
            return BotSendResult(
                ok=False,
                status="skipped:not_configured",
                error="Бот недоступен для отправки сообщений.",
            )

        if not BOT_RUNTIME_AVAILABLE or not self.configured:
            return BotSendResult(
                ok=False,
                status="skipped:not_configured",
                error="Бот не настроен.",
            )

        try:
            bot = get_bot()
        except Exception as exc:  # pragma: no cover - runtime guard
            logger.exception("Bot runtime unavailable for chat message: %s", exc)
            return BotSendResult(
                ok=False,
                status="skipped:not_configured",
                error="Бот недоступен.",
            )

        try:
            response = await bot.send_message(telegram_id, text, reply_markup=reply_markup)
        except Exception as exc:  # pragma: no cover - network errors
            if _is_transient_error(exc):
                logger.exception("Transient error while sending chat message")
                return BotSendResult(
                    ok=False,
                    status="queued_retry",
                    error=self.transient_message,
                )
            logger.exception("Failed to send chat message to %s", telegram_id)
            return BotSendResult(
                ok=False,
                status="failed",
                error=self.failure_message,
            )

        return BotSendResult(
            ok=True,
            status="sent",
            telegram_message_id=getattr(response, "message_id", None),
        )


_bot_service: Optional[BotService] = None
_null_bot_service: Optional[BotService] = None


def _create_null_bot_service() -> BotService:
    """Create a null bot service for test/dev environments where bot is optional."""

    # Create a dummy state manager - use _DummyStateManager as safe fallback
    if BOT_RUNTIME_AVAILABLE:
        try:
            from backend.apps.bot.state_store import InMemoryStateStore
            store = InMemoryStateStore(ttl_seconds=300)
            dummy_state_manager = StateManager(store)  # type: ignore
        except Exception:
            dummy_state_manager = _DummyStateManager()  # type: ignore
    else:
        dummy_state_manager = _DummyStateManager()  # type: ignore

    dummy_switch = IntegrationSwitch(initial=False)

    return BotService(
        state_manager=dummy_state_manager,
        enabled=False,
        configured=False,
        integration_switch=dummy_switch,
        required=False,
        skip_message="Bot service not configured (test/dev mode)",
    )


def configure_bot_service(service: BotService) -> None:
    """Register the bot service as a global singleton for background usage."""

    global _bot_service
    _bot_service = service


def get_bot_service(allow_null: bool = True) -> BotService:
    """Return the globally configured bot service.

    Args:
        allow_null: If True, return a null bot service in test/dev when not configured.
                   If False, raise RuntimeError (production behavior).
    """

    if _bot_service is None:
        if not allow_null:
            raise RuntimeError("Bot service is not configured")

        # In test/dev mode, return a null bot service that safely no-ops
        global _null_bot_service
        if _null_bot_service is None:
            _null_bot_service = _create_null_bot_service()
        return _null_bot_service

    return _bot_service


def provide_bot_service(request: Request) -> BotService:
    """FastAPI dependency provider for the bot service."""

    # First check app.state (set by setup_bot_state or test fixtures)
    service = getattr(request.app.state, "bot_service", None)
    if service is not None:
        return service

    # Then check if global bot service was configured
    if _bot_service is not None:
        return _bot_service

    # Finally, return null bot service for graceful degradation
    return get_bot_service(allow_null=True)


__all__ = [
    "BotSendResult",
    "BotService",
    "BOT_RUNTIME_AVAILABLE",
    "configure_bot_service",
    "get_bot_service",
    "provide_bot_service",
]


def _is_transient_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if isinstance(exc, (_AioHttpClientError, TimeoutError, ConnectionError)):
        return True
    return any(keyword in message for keyword in ("timeout", "temporar", "try again"))
