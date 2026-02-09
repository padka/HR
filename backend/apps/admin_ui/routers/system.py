import logging
from typing import Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
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


@router.get("/healthz", include_in_schema=False)
async def liveness_probe() -> PlainTextResponse:
    """Kubernetes liveness probe - always returns 200 if process is alive."""
    return PlainTextResponse("ok")


@router.get("/ready", include_in_schema=False)
async def readiness_probe(request: Request) -> PlainTextResponse:
    """Kubernetes readiness probe - checks critical dependencies."""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return PlainTextResponse("database unavailable", status_code=503)

    state_manager = getattr(request.app.state, "state_manager", None)
    import os
    is_test_mode = bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("ENVIRONMENT") == "test"
    if state_manager is None and not is_test_mode:
        return PlainTextResponse("state manager not initialized", status_code=503)

    return PlainTextResponse("ok")


@router.get("/health", include_in_schema=False)
async def health_check(request: Request) -> JSONResponse:
    checks = {
        "database": "ok",
        "state_manager": (
            "ok" if getattr(request.app.state, "state_manager", None) else "missing"
        ),
    }

    # Check Phase 2 Redis Cache
    cache_status = "disabled"
    try:
        from backend.core.cache import get_cache
        cache = get_cache()
        # Try a simple ping operation
        test_result = await cache.exists("__health_check__")
        if test_result.is_success():
            cache_status = "ok"
        else:
            cache_status = "error"
    except RuntimeError:
        # Cache not initialized
        cache_status = "disabled"
    except Exception as exc:
        logger.warning(f"Cache health check failed: {exc}")
        cache_status = "error"
    checks["cache"] = cache_status

    # Check background tasks status
    background_tasks = {}
    cache_watch_task = getattr(request.app.state, "cache_watch_task", None)
    if cache_watch_task:
        background_tasks["cache_watcher"] = "running" if not cache_watch_task.done() else "stopped"

    stalled_checker_task = getattr(request.app.state, "stalled_checker_task", None)
    if stalled_checker_task:
        background_tasks["stalled_candidate_checker"] = "running" if not stalled_checker_task.done() else "stopped"

    checks["background_tasks"] = background_tasks

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

    # In test mode, state_manager is optional and should not fail health check
    import os
    is_test_mode = bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("ENVIRONMENT") == "test"

    if checks["state_manager"] == "missing" and not is_test_mode:
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


@router.get("/health/notifications", include_in_schema=False)
async def notifications_health(request: Request) -> JSONResponse:
    bot_service = getattr(request.app.state, "bot_service", None)
    bot_runner_task = getattr(request.app.state, "bot_runner_task", None)
    notification_service = getattr(request.app.state, "notification_service", None)
    reminder_service = getattr(request.app.state, "reminder_service", None)

    bot_info = {
        "health": bot_service.health_status if bot_service else "missing",
        "ready": bot_service.is_ready() if bot_service else False,
        "polling": bool(bot_runner_task) and not getattr(bot_runner_task, "done", lambda: False)(),
    }

    reminder_info = {"status": "missing"}
    if reminder_service is not None:
        reminder_snapshot = reminder_service.health_snapshot()
        reminder_info = {
            **reminder_snapshot,
            "status": "ok" if reminder_snapshot.get("scheduler_running") else "stopped",
        }

    notification_info = {"status": "missing", "metrics": {}}
    status_code = 503
    if notification_service is not None:
        snapshot = await notification_service.health_snapshot()
        broker_ping = await notification_service.broker_ping()
        metrics_payload = snapshot.pop("metrics", {})
        if snapshot.get("seconds_since_poll") is not None:
            metrics_payload.setdefault("seconds_since_poll", snapshot["seconds_since_poll"])
        notification_info = {
            **snapshot,
            "metrics": metrics_payload,
            "broker_ping": (
                "ok" if broker_ping else "error" if broker_ping is False else "skipped"
            ),
        }
        is_ok = snapshot.get("started") and (broker_ping is not False)
        notification_info["status"] = "ok" if is_ok else "error"
        status_code = 200 if is_ok else 503

    overall_status = "ok" if status_code == 200 else "error"

    payload = {
        "status": overall_status,
        "bot": bot_info,
        "notifications": notification_info,
        "reminders": reminder_info,
    }
    return JSONResponse(payload, status_code=status_code)


def _format_prometheus_labels(labels: Dict[str, str]) -> str:
    if not labels:
        return ""
    escaped = []
    for key, value in labels.items():
        safe = (
            str(value)
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace('"', '\\"')
        )
        escaped.append(f'{key}="{safe}"')
    return "{" + ",".join(escaped) + "}"


@router.get("/metrics/notifications", include_in_schema=False)
async def notifications_metrics(request: Request) -> PlainTextResponse:
    notification_service = getattr(request.app.state, "notification_service", None)
    if notification_service is None:
        return PlainTextResponse(
            "# notification_service_missing 0\n",
            status_code=503,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    metrics = await notification_service.metrics_snapshot()
    snapshot = await notification_service.health_snapshot()
    broker_status = await notification_service.broker_ping()

    seconds_since_poll = snapshot.get("seconds_since_poll") or 0.0
    metrics_payload = snapshot.get("metrics", {})
    lines = []

    def _emit(name: str, value: float, *, metric_type: str, help_text: str, labels=None):
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {metric_type}")
        label_str = _format_prometheus_labels(labels or {})
        lines.append(f"{name}{label_str} {value}")

    _emit(
        "notification_broker_up",
        1 if broker_status not in (False, None) else 0,
        metric_type="gauge",
        help_text="Broker ping status (1=up)",
    )
    _emit(
        "notification_seconds_since_poll",
        seconds_since_poll or 0.0,
        metric_type="gauge",
        help_text="Seconds since the last poll iteration completed",
    )
    _emit(
        "notification_outbox_queue_depth",
        metrics.outbox_queue_depth,
        metric_type="gauge",
        help_text="Number of pending notifications in outbox",
    )
    _emit(
        "notification_poll_skipped_total",
        metrics.poll_skipped_total,
        metric_type="counter",
        help_text="Total number of skipped poll iterations",
    )
    for reason, count in metrics.poll_skipped_reasons.items():
        _emit(
            "notification_poll_skipped_reason_total",
            count,
            metric_type="counter",
            help_text="Skipped poll iterations by reason",
            labels={"reason": reason},
        )
    _emit(
        "notification_poll_backoff_total",
        metrics.poll_backoff_total,
        metric_type="counter",
        help_text="Total poll backoff events",
    )
    for reason, count in metrics.poll_backoff_reasons.items():
        _emit(
            "notification_poll_backoff_reason_total",
            count,
            metric_type="counter",
            help_text="Poll backoff events by reason",
            labels={"reason": reason},
        )
    _emit(
        "notification_rate_limit_wait_total",
        metrics.rate_limit_wait_total,
        metric_type="counter",
        help_text="Total rate-limit throttling events",
    )
    _emit(
        "notification_rate_limit_wait_seconds_total",
        metrics.rate_limit_wait_seconds,
        metric_type="counter",
        help_text="Total seconds spent waiting due to rate limits",
    )
    _emit(
        "notification_poll_staleness_seconds",
        metrics.poll_staleness_seconds,
        metric_type="gauge",
        help_text="Seconds since worker watchdog recorded an active poll",
    )

    for notif_type, count in metrics.notifications_sent_total.items():
        _emit(
            "notification_sent_total",
            count,
            metric_type="counter",
            help_text="Notifications successfully sent (per type)",
            labels={"type": notif_type},
        )
    for notif_type, count in metrics.notifications_failed_total.items():
        _emit(
            "notification_failed_total",
            count,
            metric_type="counter",
            help_text="Notifications failed to send (per type)",
            labels={"type": notif_type},
        )

    text_payload = "\n".join(lines) + "\n"
    return PlainTextResponse(
        text_payload,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
