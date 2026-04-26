import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from backend.apps.admin_api.admin import mount_admin
from backend.apps.admin_api.candidate_access.router import (
    router as candidate_access_router,
)
from backend.apps.admin_api.candidate_web import (
    api_router as candidate_web_api_router,
)
from backend.apps.admin_api.candidate_web import (
    shell_router as candidate_web_shell_router,
)
from backend.apps.admin_api.hh_integration import router as hh_integration_router
from backend.apps.admin_api.hh_sync import router as hh_sync_router
from backend.apps.admin_api.max_launch import router as max_launch_router
from backend.apps.admin_api.max_miniapp import router as max_miniapp_router
from backend.apps.admin_api.max_webhook import router as max_webhook_router
from backend.apps.admin_api.slot_assignments import router as slot_assignments_router
from backend.apps.admin_api.webapp.recruiter_routers import (
    router as recruiter_webapp_router,
)
from backend.apps.admin_api.webapp.routers import router as webapp_router
from backend.apps.admin_ui.middleware import (
    CacheHeadersMiddleware,
    RequestIDMiddleware,
    SecureHeadersMiddleware,
)
from backend.core.cache import (
    CacheConfig,
    connect_cache,
    disconnect_cache,
    get_cache,
    init_cache,
)
from backend.core.db import async_engine, async_session
from backend.core.logging import configure_logging
from backend.core.messenger.bootstrap import ensure_max_adapter
from backend.core.messenger.max_recovery import MaxDeliveryRecoveryWorker
from backend.core.messenger.protocol import MessengerPlatform
from backend.core.messenger.registry import unregister_adapter
from backend.core.settings import get_settings

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SPA_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
SPA_MANIFEST_FILE = SPA_DIST_DIR / "manifest.json"
SPA_ICONS_DIR = SPA_DIST_DIR / "icons"


def _max_launch_validation_detail(exc: RequestValidationError) -> dict[str, str]:
    errors = exc.errors()
    normalized_locations = [
        ".".join(str(part) for part in error.get("loc", ()))
        for error in errors
        if isinstance(error, dict)
    ]
    if any(location.endswith("init_data") for location in normalized_locations):
        return {
            "code": "invalid_init_data",
            "message": "Откройте кабинет внутри MAX, чтобы передать корректный launch-контекст.",
        }
    return {
        "code": "invalid_launch_request",
        "message": "MAX launch request is invalid.",
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # NOTE: Database migrations should be run separately before starting the app
    # Run: python scripts/run_migrations.py

    settings = get_settings()

    # Initialize Phase 2 Performance Cache
    redis_url = settings.redis_url
    if redis_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(redis_url)

            cache_config = CacheConfig(
                host=parsed.hostname or "localhost",
                port=parsed.port or 6379,
                db=int(parsed.path.strip("/") or "0") if parsed.path else 0,
                password=parsed.password,
            )
            init_cache(cache_config)
            await connect_cache()
            logger.info(f"✓ Phase 2 Cache initialized: {parsed.hostname}:{parsed.port}")
        except Exception as e:
            if settings.environment == "production":
                raise RuntimeError(f"Failed to initialize cache in production: {e}") from e
            else:
                logger.warning(f"Cache initialization failed (non-production): {e}")
    else:
        logger.info("Cache disabled (no REDIS_URL)")

    max_adapter = None
    recovery_worker = None
    try:
        try:
            max_adapter = await ensure_max_adapter(settings=settings)
        except Exception:
            logger.exception("admin_api.max_adapter_bootstrap_failed")
        if settings.max_adapter_enabled and settings.max_delivery_recovery_admin_api_enabled:
            recovery_worker = MaxDeliveryRecoveryWorker(settings=settings)
            recovery_worker.start()
            app.state.max_delivery_recovery_worker = recovery_worker
        yield
    finally:
        if recovery_worker is not None:
            try:
                await recovery_worker.shutdown()
            except Exception:
                logger.debug("admin_api.max_delivery_recovery_shutdown_error", exc_info=True)
        if max_adapter is not None:
            try:
                await max_adapter.close()
            except Exception:
                logger.debug("admin_api.max_adapter_close_error", exc_info=True)
            unregister_adapter(MessengerPlatform.MAX)
        # Disconnect cache
        try:
            await disconnect_cache()
        except Exception:
            logger.debug("admin_api.cache_disconnect_error", exc_info=True)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(title="TG Bot Admin API", lifespan=lifespan)
    assets_dir = SPA_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa-assets")
        logger.info("SPA assets mounted at /assets")
    else:
        logger.warning("SPA assets directory not found at %s. Build frontend to enable /miniapp.", assets_dir)
    if SPA_ICONS_DIR.exists():
        app.mount("/icons", StaticFiles(directory=str(SPA_ICONS_DIR)), name="spa-icons")
        logger.info("SPA icons mounted at /icons")
    else:
        logger.warning("SPA icons directory not found at %s.", SPA_ICONS_DIR)

    @app.get("/manifest.json", include_in_schema=False, response_class=FileResponse)
    async def spa_manifest() -> FileResponse:
        if not SPA_MANIFEST_FILE.exists():
            raise HTTPException(status_code=404, detail="SPA manifest is not available.")
        return FileResponse(str(SPA_MANIFEST_FILE))

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError):
        if request.url.path == "/api/max/launch":
            detail = _max_launch_validation_detail(exc)
            logger.warning("admin_api.max_launch_request_invalid", extra={"code": detail["code"]})
            return JSONResponse(status_code=422, content={"detail": detail})
        return await request_validation_exception_handler(request, exc)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site=settings.session_cookie_samesite,
        https_only=settings.session_cookie_secure,
    )
    app.add_middleware(SecureHeadersMiddleware)
    app.add_middleware(CacheHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    mount_admin(app, async_engine)

    # Mount WebApp API endpoints for Telegram Mini App
    app.include_router(webapp_router, prefix="/api/webapp", tags=["webapp"])
    logger.info("WebApp API router mounted at /api/webapp")

    # Mount bounded MAX mini-app launch boundary
    app.include_router(max_launch_router, prefix="/api/max", tags=["max"])
    logger.info("MAX API router mounted at /api/max")
    app.include_router(max_webhook_router, prefix="/api/max", tags=["max"])
    logger.info("MAX webhook router mounted at /api/max")
    app.include_router(max_miniapp_router)
    logger.info("MAX mini-app shell mounted at /miniapp")

    # Mount shared candidate-access API for candidate-facing surfaces
    app.include_router(candidate_access_router, prefix="/api/candidate-access", tags=["candidate-access"])
    logger.info("Candidate access API router mounted at /api/candidate-access")

    # Mount bounded browser candidate pilot surface. The shell and API stay
    # separate from legacy /candidate* and Telegram/MAX contracts.
    app.include_router(candidate_web_shell_router)
    app.include_router(candidate_web_api_router, prefix="/api/candidate-web", tags=["candidate-web"])
    logger.info("Browser candidate pilot mounted at /candidate-flow and /api/candidate-web")

    # Mount Recruiter WebApp API endpoints for Telegram Mini App
    app.include_router(recruiter_webapp_router, prefix="/api/webapp/recruiter", tags=["webapp-recruiter"])
    logger.info("Recruiter WebApp API router mounted at /api/webapp/recruiter")

    # Bot-facing slot assignment endpoints
    app.include_router(slot_assignments_router)

    # hh.ru sync callback endpoints (called by n8n)
    app.include_router(hh_sync_router)
    app.include_router(hh_integration_router)

    @app.get("/")
    async def root():
        return {"ok": True, "admin": "/admin", "webapp_api": "/api/webapp", "health": "/health"}

    async def _health_payload() -> tuple[dict[str, Any], int]:
        start_time = time.time()
        components: dict[str, dict[str, Any]] = {
            "application": {"status": "up"},
        }
        overall_status = "healthy"
        current_settings = get_settings()

        db_start = time.time()
        try:
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
            db_latency = (time.time() - db_start) * 1000
            components["database"] = {
                "status": "up",
                "latency_ms": round(db_latency, 2),
            }
        except Exception:
            overall_status = "unhealthy"
            components["database"] = {
                "status": "down",
                "error": "database_unavailable",
            }

        if current_settings.redis_url:
            redis_start = time.time()
            try:
                cache = get_cache()
                await cache.ping()
                redis_latency = (time.time() - redis_start) * 1000
                components["redis"] = {
                    "status": "up",
                    "latency_ms": round(redis_latency, 2),
                }
            except RuntimeError:
                overall_status = "unhealthy"
                components["redis"] = {
                    "status": "down",
                    "error": "cache_not_initialized",
                }
            except Exception:
                overall_status = "unhealthy"
                components["redis"] = {
                    "status": "down",
                    "error": "redis_unavailable",
                }
        else:
            if current_settings.environment == "production":
                overall_status = "degraded"
            components["redis"] = {
                "status": "not_configured",
                "note": "Redis is not configured",
            }

        payload = {
            "status": overall_status,
            "timestamp": datetime.now(UTC).isoformat(),
            "components": components,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
        }
        status_code = 503 if overall_status == "unhealthy" else 200
        return payload, status_code

    @app.get("/healthz", include_in_schema=False)
    async def live_check():
        return {"status": "ok"}

    @app.get("/ready", include_in_schema=False)
    async def ready_check():
        payload, status_code = await _health_payload()
        return JSONResponse(content=payload, status_code=status_code)

    @app.get("/health")
    async def health_check():
        """
        Health check endpoint for monitoring and load balancers.

        Returns:
            - 200 if all components are healthy
            - 503 if any component is unhealthy
        """
        payload, status_code = await _health_payload()
        return JSONResponse(content=payload, status_code=status_code)

    return app


app = create_app()
