"""FastAPI application wiring for the admin UI."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from backend.apps.admin_ui.config import STATIC_DIR, register_template_globals
from backend.apps.admin_ui.routers import (
    api,
    cities,
    dashboard,
    questions,
    recruiters,
    slots,
    system,
    templates,
)
from backend.apps.admin_ui.security import require_admin
from backend.apps.admin_ui.state import BotIntegration, setup_bot_state
from backend.core.db import init_models
from backend.core.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    register_template_globals()
    integration: BotIntegration = await setup_bot_state(app)
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    logging.warning("ROUTES LOADED: %s", routes)
    try:
        yield
    finally:
        await integration.shutdown()


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
    app.include_router(recruiters.router, dependencies=[Depends(require_admin)])
    app.include_router(cities.router, dependencies=[Depends(require_admin)])
    app.include_router(templates.router, dependencies=[Depends(require_admin)])
    app.include_router(questions.router, dependencies=[Depends(require_admin)])
    app.include_router(api.router, dependencies=[Depends(require_admin)])

    return app


app = create_app()

__all__ = ["app", "create_app", "lifespan"]
