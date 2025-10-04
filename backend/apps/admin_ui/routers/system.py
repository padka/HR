import logging
from typing import Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy import text

from backend.apps.admin_ui.services.bot_service import (
    BOT_RUNTIME_AVAILABLE,
    IntegrationSwitch,
)
from backend.core.db import async_session
from backend.core.settings import get_settings

try:  # pragma: no cover - optional dependency handling
    from backend.apps.bot.services import get_bot
except Exception:  # pragma: no cover - optional dependency
    get_bot = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/favicon.ico", include_in_schema=False)
async def favicon_redirect() -> RedirectResponse:
    return RedirectResponse(url="/static/favicon.ico")


@router.get(
    "/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False
)
async def devtools_probe() -> Response:
    return Response(status_code=204)


@router.get("/health", include_in_schema=False)
async def health_check(request: Request) -> JSONResponse:
    checks = {
        "database": "ok",
        "state_manager": (
            "ok" if getattr(request.app.state, "state_manager", None) else "missing"
        ),
    }
    bot_service = getattr(request.app.state, "bot_service", None)
    bot_client_status = bot_service.health_status if bot_service else "missing"
    checks["bot_client"] = bot_client_status
    switch: IntegrationSwitch | None = getattr(
        request.app.state, "bot_integration_switch", None
    )
    if switch is not None:
        checks["bot_integration"] = "enabled" if switch.is_enabled() else "disabled"

    if bot_client_status == "ready":
        checks["bot"] = "configured"
    elif bot_client_status == "missing":
        checks["bot"] = "missing"
    elif bot_client_status in {"disabled", "disabled_runtime"}:
        checks["bot"] = "disabled"
    else:
        checks["bot"] = "unconfigured"
    status_code = 200

    if checks["state_manager"] == "missing":
        status_code = 503

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - depends on runtime DB availability
        logger.exception("Health check database probe failed")
        checks["database"] = "error"
        status_code = 503

    return JSONResponse(
        {"status": "ok" if status_code == 200 else "error", "checks": checks},
        status_code=status_code,
    )


@router.get("/health/bot", include_in_schema=False)
async def bot_health(request: Request) -> JSONResponse:
    settings = get_settings()
    bot_service = getattr(request.app.state, "bot_service", None)
    switch: IntegrationSwitch | None = getattr(
        request.app.state, "bot_integration_switch", None
    )
    state_manager = getattr(request.app.state, "state_manager", None)

    enabled = settings.bot_enabled
    runtime_enabled = (
        switch.is_enabled() if switch else settings.bot_integration_enabled
    )
    service_health = bot_service.health_status if bot_service else "missing"
    service_ready = bot_service.is_ready() if bot_service else False
    mode = (
        "real"
        if bot_service and bot_service.configured and BOT_RUNTIME_AVAILABLE
        else "null"
    )

    telegram_probe: Dict[str, object]
    if not enabled:
        telegram_probe = {"ok": False, "error": "bot_feature_disabled"}
    elif not runtime_enabled:
        telegram_probe = {"ok": False, "error": "integration_disabled"}
    elif bot_service is None or not bot_service.configured or not BOT_RUNTIME_AVAILABLE:
        telegram_probe = {"ok": False, "error": "bot_not_configured"}
    elif get_bot is None:
        telegram_probe = {"ok": False, "error": "runtime_unavailable"}
    else:
        try:
            bot = get_bot()
            me = await bot.get_me()
            telegram_probe = {"ok": True, "id": me.id, "username": me.username}
        except Exception as exc:  # pragma: no cover - network/environment errors
            telegram_probe = {"ok": False, "error": str(exc)}

    state_metrics: Dict[str, object] = {}
    if state_manager is not None and hasattr(state_manager, "metrics"):
        metrics = state_manager.metrics
        backend = getattr(
            getattr(state_manager, "_store", None), "__class__", type("", (), {})
        ).__name__
        state_metrics = {
            "backend": backend,
            "hits": metrics.state_hits,
            "misses": metrics.state_misses,
            "evictions": metrics.state_evictions,
        }

    reminder_service = getattr(request.app.state, "reminder_service", None)
    if reminder_service is not None:
        queues = reminder_service.stats()
    else:
        queues = {"total": 0, "confirm_prompts": 0, "reminders": 0}

    payload = {
        "config": {
            "bot_enabled": enabled,
            "integration_enabled": settings.bot_integration_enabled,
        },
        "runtime": {
            "switch_enabled": runtime_enabled,
            "switch_updated_at": switch.updated_at.isoformat() if switch else None,
            "service_health": service_health,
            "service_ready": service_ready,
            "mode": mode,
        },
        "telegram": telegram_probe,
        "state_store": state_metrics,
        "queues": queues,
    }
    return JSONResponse(payload)
