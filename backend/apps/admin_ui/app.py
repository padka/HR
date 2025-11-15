"""FastAPI application wiring for the admin UI."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlparse
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette_wtf import CSRFProtectMiddleware

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
)
from backend.apps.admin_ui.security import require_admin
from backend.apps.admin_ui.state import BotIntegration, setup_bot_state
from backend.core.logging import configure_logging
from backend.core.settings import get_settings
from backend.core.cache import CacheConfig, init_cache, connect_cache, disconnect_cache, get_cache
from backend.core.error_handler import (
    setup_global_exception_handler,
    resilient_task,
    GracefulShutdown,
)

configure_logging()
request_logger = logging.getLogger("tg.admin.requests")
logger = logging.getLogger(__name__)

CACHE_RETRY_ATTEMPTS = 5
CACHE_RETRY_BASE_DELAY = 1.0
CACHE_RETRY_MAX_DELAY = 30.0
CACHE_HEALTH_INTERVAL = 15.0


def _build_cache_config(redis_url: str) -> CacheConfig:
    parsed = urlparse(redis_url)
    return CacheConfig(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        db=int(parsed.path.strip("/") or "0") if parsed.path else 0,
        password=parsed.password,
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
        if settings.environment == "production":
            logging.warning("⚠ REDIS_URL not set in production - cache disabled")
        else:
            logging.info("Cache disabled (no REDIS_URL)")
        return None

    try:
        cache_config = _build_cache_config(redis_url)
    except Exception as exc:
        logging.error("Failed to parse REDIS_URL for cache: %s", exc)
        return None

    init_cache(cache_config)
    success = await _connect_cache_with_retry()
    if success:
        app.state.cache_status = "ok"
    else:
        app.state.cache_status = "degraded"
        logging.error("Cache initialized in degraded mode; will retry in background.")

    task = asyncio.create_task(_cache_health_watcher(app))
    app.state.cache_watch_task = task
    return task

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
    shutdown_manager = GracefulShutdown(timeout=15.0)

    # Initialize cache with retry logic
    cache_task = None
    try:
        cache_task = await _initialize_cache_with_supervisor(app, settings)
        if cache_task:
            shutdown_manager.add_task(cache_task)
            logger.info("Cache supervisor started")
    except Exception as exc:
        logger.error("Cache supervisor failed to start: %s", exc, exc_info=True)

    # Start background task for stalled candidate checker (runs hourly)
    stalled_checker_task = None
    try:
        stalled_checker_task = asyncio.create_task(
            periodic_stalled_candidate_checker(interval_hours=1),
            name="stalled_candidate_checker",
        )
        app.state.stalled_checker_task = stalled_checker_task
        shutdown_manager.add_task(stalled_checker_task)
        logger.info("Stalled candidate checker started")
    except Exception as exc:
        logger.error("Failed to start stalled candidate checker: %s", exc, exc_info=True)

    # Initialize templates and bot integration
    try:
        register_template_globals()
        integration: BotIntegration = await setup_bot_state(app)
        logger.info("Bot integration initialized")
    except Exception as exc:
        logger.error("Failed to initialize bot integration: %s", exc, exc_info=True)
        raise

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

    app = FastAPI(
        title="TG Bot Admin UI",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
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
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(system.router)
    app.include_router(dashboard.router, dependencies=[Depends(require_admin)])
    app.include_router(slots.router, dependencies=[Depends(require_admin)])
    app.include_router(candidates.router, dependencies=[Depends(require_admin)])
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
            raise
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
