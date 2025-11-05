"""FastAPI application wiring for the admin UI."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

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
from backend.core.settings import get_settings
from backend.core.cache import CacheConfig, init_cache, connect_cache, disconnect_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    # NOTE: Database migrations should be run separately before starting the app
    # Run: python scripts/run_migrations.py

    settings = get_settings()

    # Initialize Phase 2 Performance Cache
    redis_url = settings.redis_url
    if redis_url:
        try:
            # Parse Redis URL to extract host/port
            # Format: redis://host:port/db or redis://host:port
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
            logging.info(f"✓ Phase 2 Cache initialized: {parsed.hostname}:{parsed.port}")
        except Exception as e:
            if settings.environment == "production":
                raise RuntimeError(f"Failed to initialize cache in production: {e}") from e
            else:
                logging.warning(f"Cache initialization failed (non-production): {e}")
    else:
        if settings.environment == "production":
            logging.warning("⚠ REDIS_URL not set in production - cache disabled")
        else:
            logging.info("Cache disabled (no REDIS_URL)")

    register_template_globals()
    integration: BotIntegration = await setup_bot_state(app)
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    logging.warning("ROUTES LOADED: %s", routes)
    try:
        yield
    finally:
        await integration.shutdown()
        # Disconnect cache
        try:
            await disconnect_cache()
        except Exception:
            pass


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

    return app


app = create_app()

__all__ = ["app", "create_app", "lifespan"]
