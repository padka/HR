from contextlib import asynccontextmanager
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text

from backend.core.db import async_engine, async_session
from backend.apps.admin_api.admin import mount_admin
from backend.apps.admin_api.webapp.routers import router as webapp_router
from backend.apps.admin_api.slot_assignments import router as slot_assignments_router
from backend.core.settings import get_settings
from backend.core.cache import CacheConfig, init_cache, connect_cache, disconnect_cache, get_cache

logger = logging.getLogger(__name__)


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

    try:
        yield
    finally:
        # Disconnect cache
        try:
            await disconnect_cache()
        except Exception:
            logger.debug("admin_api.cache_disconnect_error", exc_info=True)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="TG Bot Admin API", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site=settings.session_cookie_samesite,
        https_only=settings.session_cookie_secure,
    )
    mount_admin(app, async_engine)

    # Mount WebApp API endpoints for Telegram Mini App
    app.include_router(webapp_router, prefix="/api/webapp", tags=["webapp"])
    logger.info("WebApp API router mounted at /api/webapp")

    # Bot-facing slot assignment endpoints
    app.include_router(slot_assignments_router)

    @app.get("/")
    async def root():
        return {"ok": True, "admin": "/admin", "webapp_api": "/api/webapp", "health": "/health"}

    @app.get("/health")
    async def health_check():
        """
        Health check endpoint for monitoring and load balancers.

        Returns:
            - 200 if all components are healthy
            - 503 if any component is unhealthy
        """
        start_time = time.time()
        components: Dict[str, Dict[str, Any]] = {}
        overall_status = "healthy"
        settings = get_settings()

        # 1. Application health (always up if we're responding)
        components["application"] = {"status": "up"}

        # 2. Database health check
        db_start = time.time()
        try:
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
            db_latency = (time.time() - db_start) * 1000
            components["database"] = {
                "status": "up",
                "latency_ms": round(db_latency, 2)
            }
        except Exception as e:
            overall_status = "unhealthy"
            components["database"] = {
                "status": "down",
                "error": str(e)
            }

        # 3. Redis health check (if configured)
        if settings.redis_url:
            redis_start = time.time()
            try:
                cache = get_cache()
                if cache:
                    # Try to ping Redis
                    await cache.ping()
                    redis_latency = (time.time() - redis_start) * 1000
                    components["redis"] = {
                        "status": "up",
                        "latency_ms": round(redis_latency, 2)
                    }
                else:
                    # Redis configured but cache not initialized
                    overall_status = "degraded"
                    components["redis"] = {
                        "status": "down",
                        "error": "Cache not initialized"
                    }
            except Exception as e:
                overall_status = "unhealthy"
                components["redis"] = {
                    "status": "down",
                    "error": str(e)
                }
        else:
            # Redis not configured (acceptable in non-production)
            if settings.environment == "production":
                overall_status = "degraded"
            components["redis"] = {
                "status": "not_configured",
                "note": "Redis is not configured"
            }

        # Build response
        response_data = {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": components,
            "response_time_ms": round((time.time() - start_time) * 1000, 2)
        }

        # Return 503 if unhealthy, 200 otherwise
        status_code = 503 if overall_status == "unhealthy" else 200
        return JSONResponse(content=response_data, status_code=status_code)

    return app


app = create_app()
