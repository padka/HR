"""FastAPI application wiring for the admin UI."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_wtf import CSRFProtectMiddleware
from sqlalchemy import text
from starlette.responses import Response, PlainTextResponse

from backend.apps.admin_ui.background_tasks import periodic_stalled_candidate_checker
from backend.apps.admin_ui.config import STATIC_DIR, register_template_globals
from backend.apps.admin_ui.routers import (
    api,
    candidates,
    cities,
    dashboard,
    message_templates,
    questions,
    recruiters,
    slots,
    system,
    templates,
    workflow,
)
from backend.apps.admin_ui.security import (
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    limiter,
    require_admin,
)
from backend.apps.admin_ui.state import BotIntegration, setup_bot_state
from backend.apps.admin_ui.middleware import SecureHeadersMiddleware, DegradedDatabaseMiddleware
from backend.core.logging import configure_logging
from backend.core.settings import get_settings
from backend.core.db import async_session
from backend.core.cache import CacheConfig, init_cache, connect_cache, disconnect_cache, get_cache
from backend.core.error_handler import (
    setup_global_exception_handler,
    resilient_task,
    GracefulShutdown,
)
from backend.migrations.runner import upgrade_to_head
from backend.core.redis_factory import parse_redis_target
from sqlalchemy.exc import OperationalError
from fastapi.responses import HTMLResponse, JSONResponse

configure_logging()
request_logger = logging.getLogger("tg.admin.requests")
logger = logging.getLogger(__name__)

CACHE_RETRY_ATTEMPTS = 5
CACHE_RETRY_BASE_DELAY = 1.0
CACHE_RETRY_MAX_DELAY = 30.0
CACHE_HEALTH_INTERVAL = 15.0
DB_HEALTH_INTERVAL = 15.0
DB_HEALTH_MAX_INTERVAL = 60.0


def _build_cache_config(redis_url: str) -> CacheConfig:
    target = parse_redis_target(redis_url, component="cache")
    return CacheConfig(
        host=target.host,
        port=target.port,
        db=target.db,
        password=target.password,
    )


async def _connect_cache_with_retry(attempts: int = CACHE_RETRY_ATTEMPTS) -> bool:
    delay = CACHE_RETRY_BASE_DELAY
    for attempt in range(1, attempts + 1):
        try:
            await connect_cache()
            return True
        except Exception as exc:
            logging.warning(
                "Cache connection attempt %s/%s failed: %s",
                attempt,
                attempts,
                exc,
            )
            if attempt == attempts:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, CACHE_RETRY_MAX_DELAY)
    return False


@resilient_task(task_name="cache_health_watcher", retry_on_error=True, retry_delay=10.0)
async def _cache_health_watcher(app: FastAPI) -> None:
    """Monitor cache health and attempt reconnection if needed."""
    delay = CACHE_HEALTH_INTERVAL
    while True:
        await asyncio.sleep(delay)
        try:
            cache = get_cache()
        except RuntimeError:
            app.state.cache_status = "disabled"
            logger.info("Cache disabled, health watcher exiting")
            return

        try:
            if await cache.ping():
                app.state.cache_status = "ok"
                delay = CACHE_HEALTH_INTERVAL
                continue
        except Exception as exc:
            logger.debug("Cache ping failed: %s", exc)

        app.state.cache_status = "degraded"
        try:
            await connect_cache()
            app.state.cache_status = "ok"
            delay = CACHE_HEALTH_INTERVAL
            logger.info("Cache reconnected successfully")
        except Exception as exc:
            logger.warning("Cache reconnect failed: %s", exc)
            delay = min(delay * 2, CACHE_RETRY_MAX_DELAY)


async def _initialize_cache_with_supervisor(app: FastAPI, settings) -> Optional[asyncio.Task]:
    redis_url = settings.redis_url
    app.state.cache_status = "disabled"
    if not redis_url:
        app.state.redis_available = False
        if settings.environment == "production":
            logging.warning("⚠ REDIS_URL not set in production - cache disabled")
        else:
            logging.info("Cache disabled (no REDIS_URL)")
        return None

    try:
        cache_config = _build_cache_config(redis_url)
    except Exception as exc:
        logging.error("Failed to parse REDIS_URL for cache: %s", exc)
        app.state.redis_available = False
        return None

    init_cache(cache_config)
    cache_attempts = CACHE_RETRY_ATTEMPTS if settings.environment == "production" else 1
    success = await _connect_cache_with_retry(attempts=cache_attempts)
    if success:
        app.state.cache_status = "ok"
        app.state.redis_available = True
    else:
        app.state.cache_status = "degraded"
        app.state.redis_available = False
        logging.error("Cache initialized in degraded mode; will retry in background.")

    task = asyncio.create_task(_cache_health_watcher(app))
    app.state.cache_watch_task = task
    return task


async def _probe_database() -> None:
    async with async_session() as session:
        await session.execute(text("SELECT 1"))


def _auto_upgrade_schema_if_needed(settings) -> bool:
    """Run lightweight migration step in non-production environments."""
    if settings.environment == "production":
        return False
    try:
        upgrade_to_head()
        return True
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Automatic schema upgrade skipped: %s", exc)
        return False


async def _check_db_availability(app: FastAPI) -> bool:
    try:
        await _probe_database()
        app.state.db_available = True
        return True
    except Exception as exc:
        app.state.db_available = False
        logger.warning("Database unavailable during startup: %s", exc)
        return False


@resilient_task(task_name="db_health_watcher", retry_on_error=True, retry_delay=10.0)
async def _db_health_watcher(app: FastAPI) -> None:
    delay = DB_HEALTH_INTERVAL
    last_available = getattr(app.state, "db_available", True)
    while True:
        await asyncio.sleep(delay)
        try:
            await _probe_database()
        except Exception as exc:
            app.state.db_available = False
            if last_available:
                logger.warning("Database health check failed: %s", exc)
            last_available = False
            delay = min(delay * 2, DB_HEALTH_MAX_INTERVAL)
            continue

        if not last_available:
            logger.info("Database connection restored")
        app.state.db_available = True
        last_available = True
        delay = DB_HEALTH_INTERVAL


async def _db_unavailable_response(request: Request) -> Response:
    accepts = (request.headers.get("accept") or "").lower()
    payload = {"status": "degraded", "reason": "database_unavailable"}
    if "application/json" in accepts:
        return JSONResponse(payload, status_code=503)
    return HTMLResponse(
        "<h1>Service temporarily degraded</h1>"
        "<p>Database is unavailable. Please try again позже.</p>",
        status_code=503,
    )


async def _db_exception_handler(request: Request, exc: OperationalError) -> Response:
    request.app.state.db_available = False
    logger.warning("Database operation failed during request: %s", exc)
    return await _db_unavailable_response(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with graceful startup and shutdown."""
    # Set up global exception handler
    setup_global_exception_handler()
    logger.info("Starting Recruitsmart Admin UI...")

    # NOTE: Database migrations should be run separately before starting the app
    # Run: python scripts/run_migrations.py

    settings = get_settings()
    app.state.cache_watch_task = None
    app.state.db_watch_task = None
    shutdown_manager = GracefulShutdown(timeout=15.0)
    app.state.db_available = True
    app.state.redis_available = False
    app.state.notification_broker_available = False
    app.state.bot_enabled = settings.bot_enabled

    if _auto_upgrade_schema_if_needed(settings):
        logger.info("Development database migrated to latest revision")

    # Detect test mode
    import os
    is_test_mode = bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("ENVIRONMENT") == "test"

    # Check DB availability early to avoid crashing on startup.
    if not is_test_mode:
        await _check_db_availability(app)
        try:
            db_watch_task = asyncio.create_task(
                _db_health_watcher(app), name="db_health_watcher"
            )
            app.state.db_watch_task = db_watch_task
            shutdown_manager.add_task(db_watch_task)
            logger.info("Database health watcher started")
        except Exception as exc:
            logger.error(
                "Failed to start database health watcher: %s", exc, exc_info=True
            )
    else:
        logger.info("Test mode: skipping database health watcher")

    # Initialize cache with retry logic
    cache_task = None
    if not is_test_mode:
        try:
            cache_task = await _initialize_cache_with_supervisor(app, settings)
            if cache_task:
                shutdown_manager.add_task(cache_task)
                logger.info("Cache supervisor started")
        except Exception as exc:
            logger.error("Cache supervisor failed to start: %s", exc, exc_info=True)
            app.state.redis_available = False
    else:
        logger.info("Test mode: skipping cache supervisor")

    # Start background task for stalled candidate checker (runs hourly)
    stalled_checker_task = None
    if not is_test_mode:
        try:
            stalled_checker_task = asyncio.create_task(
                periodic_stalled_candidate_checker(interval_hours=1, app=app),
                name="stalled_candidate_checker",
            )
            app.state.stalled_checker_task = stalled_checker_task
            shutdown_manager.add_task(stalled_checker_task)
            logger.info("Stalled candidate checker started")
        except Exception as exc:
            logger.error("Failed to start stalled candidate checker: %s", exc, exc_info=True)
    else:
        logger.info("Test mode: skipping stalled candidate checker")

    # Initialize templates and bot integration
    try:
        register_template_globals()
        integration: BotIntegration = await setup_bot_state(app)
        logger.info("Bot integration initialized")
    except Exception as exc:
        logger.error("Failed to initialize bot integration: %s", exc, exc_info=True)
        integration = BotIntegration.null_integration()

    degraded_reasons = []
    if not app.state.db_available:
        degraded_reasons.append("db_unavailable")
    if settings.redis_url and not app.state.redis_available:
        degraded_reasons.append("redis_unavailable")
    if app.state.bot_enabled and not app.state.notification_broker_available:
        degraded_reasons.append("notification_broker_unavailable")
    if degraded_reasons:
        logger.warning("Starting in degraded mode: %s", ", ".join(degraded_reasons))
    else:
        logger.info("Startup dependencies healthy")

    routes = [r.path for r in app.routes if hasattr(r, "path")]
    logger.info("Application started with %d routes", len(routes))

    try:
        yield
    finally:
        logger.info("Shutting down application...")

        # Graceful shutdown of all background tasks
        await shutdown_manager.shutdown()

        # Shutdown bot integration
        try:
            await integration.shutdown()
            logger.info("Bot integration shut down")
        except Exception as exc:
            logger.error("Error during bot integration shutdown: %s", exc)

        # Disconnect cache
        try:
            await disconnect_cache()
            logger.info("Cache disconnected")
        except Exception as exc:
            logger.error("Error disconnecting cache: %s", exc)

        logger.info("Application shut down complete")


def create_app() -> FastAPI:
    settings = get_settings()
    docs_url = "/docs" if settings.admin_docs_enabled else None
    redoc_url = "/redoc" if settings.admin_docs_enabled else None
    openapi_url = "/openapi.json" if settings.admin_docs_enabled else None

    limiter.enabled = settings.rate_limit_enabled
    app = FastAPI(
        title="TG Bot Admin UI",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(OperationalError, _db_exception_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CSRFProtectMiddleware,
        csrf_secret=settings.session_secret,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site=settings.session_cookie_samesite,
        https_only=settings.session_cookie_secure,
    )
    app.add_middleware(DegradedDatabaseMiddleware)
    app.add_middleware(SecureHeadersMiddleware)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(system.router)
    app.include_router(dashboard.router, dependencies=[Depends(require_admin)])
    app.include_router(slots.router, dependencies=[Depends(require_admin)])
    app.include_router(candidates.router, dependencies=[Depends(require_admin)])
    app.include_router(workflow.router, dependencies=[Depends(require_admin)])
    app.include_router(recruiters.router, dependencies=[Depends(require_admin)])
    app.include_router(cities.router, dependencies=[Depends(require_admin)])
    app.include_router(templates.router, dependencies=[Depends(require_admin)])
    app.include_router(message_templates.router, dependencies=[Depends(require_admin)])
    app.include_router(questions.router, dependencies=[Depends(require_admin)])
    app.include_router(api.router, dependencies=[Depends(require_admin)])

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = (time.perf_counter() - start) * 1000
            request_logger.exception(
                "HTTP %s %s failed",
                request.method,
                request.url.path,
                extra={"path": request.url.path, "method": request.method, "duration_ms": duration},
            )
            return PlainTextResponse("Internal Server Error", status_code=500)
        duration = (time.perf_counter() - start) * 1000
        request_logger.info(
            "HTTP %s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        return response

    return app


app = create_app()

__all__ = ["app", "create_app", "lifespan"]
