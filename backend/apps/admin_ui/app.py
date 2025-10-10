"""FastAPI application wiring for the admin UI."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.security import SecurityMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.apps.admin_ui.config import STATIC_DIR, register_template_globals
from backend.apps.admin_ui.routers import (
    api,
    candidates,
    cities,
    dashboard,
    regions,
    questions,
    recruiters,
    slots,
    system,
    templates,
)
from backend.apps.admin_ui.security import require_admin
from backend.apps.admin_ui.state import BotIntegration, setup_bot_state
from backend.core.bootstrap import ensure_database_ready
from backend.core.settings import get_settings, validate_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    validate_settings(settings)
    await ensure_database_ready()
    register_template_globals()
    integration: BotIntegration = await setup_bot_state(app)
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    logging.warning("ROUTES LOADED: %s", routes)
    try:
        yield
    finally:
        await integration.shutdown()


def create_app() -> FastAPI:
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()
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
        TrustedHostMiddleware,
        allowed_hosts=list(settings.admin_trusted_hosts) or ["*"],
    )
    if settings.session_cookie_secure:
        app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(
        SecurityMiddleware,
        content_security_policy=(
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "object-src 'none'"
        ),
        content_security_policy_report_only=False,
        referrer_policy="strict-origin-when-cross-origin",
        strict_transport_security="max-age=63072000; includeSubDomains; preload",
        x_content_type_options="nosniff",
        x_frame_options="DENY",
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=settings.session_cookie_name,
        https_only=settings.session_cookie_secure,
        same_site=settings.session_cookie_samesite,
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(system.router)
    app.include_router(dashboard.router, dependencies=[Depends(require_admin)])
    app.include_router(slots.router, dependencies=[Depends(require_admin)])
    app.include_router(candidates.router, dependencies=[Depends(require_admin)])
    app.include_router(recruiters.router, dependencies=[Depends(require_admin)])
    app.include_router(cities.router, dependencies=[Depends(require_admin)])
    app.include_router(regions.router, dependencies=[Depends(require_admin)])
    app.include_router(templates.router, dependencies=[Depends(require_admin)])
    app.include_router(questions.router, dependencies=[Depends(require_admin)])
    app.include_router(api.router, dependencies=[Depends(require_admin)])

    return app


app = create_app()

__all__ = ["app", "create_app", "lifespan"]
