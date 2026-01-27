"""FastAPI application wiring for the admin UI."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from typing import Optional

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

from fastapi import Depends, FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_wtf import CSRFProtectMiddleware
from sqlalchemy import text
from starlette.responses import Response, PlainTextResponse

from backend.apps.admin_ui.background_tasks import (
    periodic_stalled_candidate_checker,
    periodic_past_free_slot_cleanup,
)
from backend.apps.admin_ui.config import STATIC_DIR, register_template_globals
from pathlib import Path
from pathlib import Path
from pathlib import Path
from pathlib import Path
from backend.apps.admin_ui.routers import (
    api,
    candidates,
    cities,
    dashboard,
    auth as auth_router,
    message_templates,
    questions,
    recruiters,
    slots,
    slot_assignments,
    system,
    templates,
    workflow,
    workflow,
    profile,
    assignments,
    reschedule_requests,
    slot_assignments_api,
)
from backend.apps.admin_ui.security import (
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    limiter,
    require_admin,
    require_principal,
)
from backend.apps.admin_ui.state import BotIntegration, setup_bot_state
from backend.apps.admin_ui.middleware import SecureHeadersMiddleware, DegradedDatabaseMiddleware, RequestIDMiddleware
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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.exception_handlers import http_exception_handler
from fastapi import HTTPException

configure_logging()
request_logger = logging.getLogger("tg.admin.requests")
logger = logging.getLogger(__name__)

CACHE_RETRY_ATTEMPTS = 5
CACHE_RETRY_BASE_DELAY = 1.0
CACHE_RETRY_MAX_DELAY = 30.0
CACHE_HEALTH_INTERVAL = 15.0
DB_HEALTH_INTERVAL = 15.0
DB_HEALTH_MAX_INTERVAL = 60.0

BASE_DIR = Path(__file__).resolve().parents[3]
SPA_DIST_DIR = BASE_DIR / "frontend" / "dist"


def _init_sentry(settings) -> bool:
    """Initialize Sentry error tracking if configured."""
    if not SENTRY_AVAILABLE:
        logger.debug("Sentry SDK not installed, error tracking disabled")
        return False

    if not settings.sentry_dsn:
        logger.debug("SENTRY_DSN not configured, error tracking disabled")
        return False

    try:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            send_default_pii=False,  # Don't send PII by default
        )
        logger.info("Sentry error tracking initialized (env=%s)", settings.environment)
        return True
    except Exception as exc:
        logger.warning("Failed to initialize Sentry: %s", exc)
        return False


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

    # Initialize Sentry error tracking early
    app.state.sentry_enabled = _init_sentry(settings)

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

    # Start background task for auto-removing past free slots
    slot_cleanup_task = None
    if not is_test_mode:
        try:
            slot_cleanup_task = asyncio.create_task(
                periodic_past_free_slot_cleanup(interval_minutes=1, grace_minutes=0, app=app),
                name="past_free_slot_cleanup",
            )
            app.state.slot_cleanup_task = slot_cleanup_task
            shutdown_manager.add_task(slot_cleanup_task)
            logger.info("Past free slot cleanup started")
        except Exception as exc:
            logger.error("Failed to start past free slot cleanup: %s", exc, exc_info=True)
    else:
        logger.info("Test mode: skipping past free slot cleanup")

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
    if settings.environment != "test":
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
    app.add_middleware(RequestIDMiddleware)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    if SPA_DIST_DIR.exists():
        assets_dir = SPA_DIST_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa-assets")
    else:
        logger.warning("SPA dist directory not found at %s. Build frontend to enable /app.", SPA_DIST_DIR)

    app.include_router(system.router)
    app.include_router(auth_router.router)
    app.include_router(dashboard.router, dependencies=[Depends(require_principal)])
    app.include_router(slots.router, dependencies=[Depends(require_principal)])
    app.include_router(slot_assignments.router, dependencies=[Depends(require_principal)])
    app.include_router(candidates.router, dependencies=[Depends(require_principal)])
    app.include_router(profile.router, dependencies=[Depends(require_principal)])
    app.include_router(workflow.router, dependencies=[Depends(require_admin)])
    app.include_router(recruiters.router, dependencies=[Depends(require_admin)])
    app.include_router(cities.router, dependencies=[Depends(require_principal)])
    app.include_router(templates.router, dependencies=[Depends(require_admin)])
    app.include_router(message_templates.router, dependencies=[Depends(require_admin)])
    app.include_router(questions.router, dependencies=[Depends(require_admin)])
    app.include_router(api.router, dependencies=[Depends(require_principal)])
    app.include_router(assignments.router, prefix="/api/v1")
    app.include_router(slot_assignments_api.router, prefix="/api")
    app.include_router(reschedule_requests.router, prefix="/api/v1/admin", dependencies=[Depends(require_principal)])

    if SPA_DIST_DIR.exists():
        @app.get("/app", include_in_schema=False)
        async def spa_index() -> Response:
            index_file = SPA_DIST_DIR / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return PlainTextResponse("SPA build not found", status_code=404)

        @app.get("/app/{path:path}", include_in_schema=False)
        async def spa_assets(path: str) -> Response:
            target = (SPA_DIST_DIR / path).resolve()
            if target.exists() and target.is_file():
                return FileResponse(target)
            index_file = SPA_DIST_DIR / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return PlainTextResponse("SPA build not found", status_code=404)

    @app.exception_handler(HTTPException)
    async def http_exc_handler(request: Request, exc: HTTPException):
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            path = request.url.path
            if path.startswith("/app") and SPA_DIST_DIR.exists():
                # Serve SPA index for client-side routes, but not for asset files.
                if "." not in Path(path).name:
                    index_file = SPA_DIST_DIR / "index.html"
                    if index_file.exists():
                        return FileResponse(index_file)
        if (
            exc.status_code == status.HTTP_401_UNAUTHORIZED
            and "text/html" in request.headers.get("accept", "")
            and not str(request.url.path).startswith("/auth")
        ):
            target = f"/auth/login?redirect_to={request.url.path}"
            return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
        return await http_exception_handler(request, exc)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        request_id = getattr(request.state, "request_id", None)
        try:
            response = await call_next(request)
        except Exception:
            duration = (time.perf_counter() - start) * 1000
            request_logger.exception(
                "HTTP %s %s failed [%s]",
                request.method,
                request.url.path,
                request_id,
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "duration_ms": duration,
                    "request_id": request_id,
                },
            )
            return PlainTextResponse("Internal Server Error", status_code=500)
        duration = (time.perf_counter() - start) * 1000
        request_logger.info(
            "HTTP %s %s -> %s (%.1f ms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration,
            request_id,
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration,
                "request_id": request_id,
            },
        )
        return response

    return app


app = create_app()

__all__ = ["app", "create_app", "lifespan"]
