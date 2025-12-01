from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from backend.core.db import async_engine
from backend.apps.admin_api.admin import mount_admin
from backend.apps.admin_api.webapp.routers import router as webapp_router
from backend.core.settings import get_settings
from backend.core.cache import CacheConfig, init_cache, connect_cache, disconnect_cache

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
            pass


def create_app() -> FastAPI:
    app = FastAPI(title="TG Bot Admin API", lifespan=lifespan)
    mount_admin(app, async_engine)

    # Mount WebApp API endpoints for Telegram Mini App
    app.include_router(webapp_router, prefix="/api/webapp", tags=["webapp"])
    logger.info("WebApp API router mounted at /api/webapp")

    @app.get("/")
    async def root():
        return {"ok": True, "admin": "/admin", "webapp_api": "/api/webapp"}

    return app


app = create_app()
