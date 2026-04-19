"""Bootstrap messenger adapters at application startup."""

from __future__ import annotations

import importlib
import inspect
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from backend.core.messenger.registry import get_registry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MaxRuntimeBootstrapConfig:
    enabled: bool
    bot_token: str
    public_bot_name: str
    miniapp_url: str

    @property
    def configured(self) -> bool:
        return bool(self.bot_token)


class MaxRuntimeDisabledError(RuntimeError):
    """Raised when the guarded MAX runtime should stay disabled."""


def _get_env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_env_str(name: str) -> str:
    return (os.getenv(name) or "").strip()


def resolve_max_runtime_bootstrap_config(
    *,
    settings: Any | None = None,
) -> MaxRuntimeBootstrapConfig:
    """Resolve the bounded MAX runtime config without requiring settings changes."""

    if settings is None:
        try:
            from backend.core.settings import get_settings

            settings = get_settings()
        except Exception:
            settings = None

    enabled = _get_env_bool(
        "MAX_ADAPTER_ENABLED",
        default=bool(getattr(settings, "max_adapter_enabled", False)),
    )
    bot_token = _get_env_str("MAX_BOT_TOKEN") or str(
        getattr(settings, "max_bot_token", "") or ""
    ).strip()
    public_bot_name = _get_env_str("MAX_PUBLIC_BOT_NAME") or str(
        getattr(settings, "max_public_bot_name", "") or ""
    ).strip()
    miniapp_url = _get_env_str("MAX_MINIAPP_URL") or str(
        getattr(settings, "max_miniapp_url", "") or ""
    ).strip()
    return MaxRuntimeBootstrapConfig(
        enabled=enabled,
        bot_token=bot_token,
        public_bot_name=public_bot_name,
        miniapp_url=miniapp_url,
    )


def describe_max_runtime_state(
    *,
    settings: Any | None = None,
) -> str:
    config = resolve_max_runtime_bootstrap_config(settings=settings)
    base_message = (
        "MAX bot runtime is disabled in the supported RecruitSmart runtime. "
        "The compose default stack does not start MAX by default."
    )
    if not config.enabled:
        return (
            f"{base_message} Set MAX_ADAPTER_ENABLED=true to opt into the bounded "
            "MAX adapter shell."
        )
    if not config.configured:
        return (
            f"{base_message} MAX_ADAPTER_ENABLED=true also requires MAX_BOT_TOKEN "
            "before the bounded MAX adapter shell can start."
        )
    return (
        "MAX bot runtime is enabled for the bounded MAX adapter shell. "
        "The default RecruitSmart runtime surface remains unchanged."
    )


def _resolve_max_shell_bootstrap(module: Any) -> Callable[..., Any]:
    bootstrap = getattr(module, "bootstrap_max_adapter_shell", None)
    if bootstrap is None:
        bootstrap = getattr(module, "run_max_adapter_shell", None)
    if bootstrap is None:
        raise RuntimeError(
            "backend.core.messenger.max_adapter does not expose a bounded MAX shell bootstrap"
        )
    if not callable(bootstrap):
        raise RuntimeError(
            "backend.core.messenger.max_adapter bounded shell bootstrap is not callable"
        )
    return bootstrap


async def _call_with_supported_kwargs(
    func: Callable[..., Any],
    **kwargs: Any,
) -> Any:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        signature = None
    if signature is None:
        result = func()
    else:
        call_kwargs = {
            name: value for name, value in kwargs.items() if name in signature.parameters
        }
        result = func(**call_kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def run_max_adapter_shell(
    *,
    settings: Any | None = None,
) -> None:
    """Run the bounded MAX adapter shell when explicitly enabled."""

    config = resolve_max_runtime_bootstrap_config(settings=settings)
    if not config.enabled or not config.configured:
        raise MaxRuntimeDisabledError(describe_max_runtime_state(settings=settings))

    try:
        module = importlib.import_module("backend.core.messenger.max_adapter")
    except ModuleNotFoundError as exc:
        if exc.name == "backend.core.messenger.max_adapter":
            raise RuntimeError(
                "MAX_ADAPTER_ENABLED=true but backend.core.messenger.max_adapter is unavailable"
            ) from exc
        raise

    bootstrap = _resolve_max_shell_bootstrap(module)
    logger.info(
        "messenger.bootstrap.max_shell_start",
        extra={
            "enabled": config.enabled,
            "configured": config.configured,
            "public_bot_name": config.public_bot_name or None,
            "has_miniapp_url": bool(config.miniapp_url),
        },
    )
    await _call_with_supported_kwargs(
        bootstrap,
        config=config,
        settings=settings,
    )


async def ensure_max_adapter(
    *,
    settings: Any | None = None,
):
    """Return a configured MAX adapter when the bounded runtime is enabled."""

    config = resolve_max_runtime_bootstrap_config(settings=settings)
    if not config.enabled or not config.configured:
        return None

    from backend.core.messenger.max_adapter import MaxAdapter
    from backend.core.messenger.protocol import MessengerPlatform

    registry = get_registry()
    existing = registry.get(MessengerPlatform.MAX)
    if existing is not None and bool(getattr(existing, "is_configured", True)):
        return existing

    adapter = MaxAdapter()
    await adapter.configure(
        token=config.bot_token,
        public_bot_name=config.public_bot_name,
        miniapp_url=config.miniapp_url,
    )
    registry.register(adapter)
    return adapter


async def bootstrap_messenger_adapters(
    *,
    bot: Any | None = None,
) -> None:
    """Register all configured messenger adapters.

    Call this once during application startup (e.g. in ``create_application()``).

    Args:
        bot: Existing aiogram Bot instance (or None for lazy resolution).
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

    # 2. MAX adapter (explicit opt-in only)
    try:
        await ensure_max_adapter()
    except Exception:
        logger.exception("messenger.bootstrap.max_failed")

    logger.info(
        "messenger.bootstrap.done",
        extra={"platforms": [p.value for p in registry.platforms]},
    )
