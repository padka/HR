"""FastAPI application wiring for the admin UI."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.core.db import init_models
from backend.apps.admin_ui.state import setup_bot_state, BotIntegration
from backend.apps.admin_ui.config import STATIC_DIR, register_template_globals
from backend.apps.admin_ui.routers import (
    api,
    cities,
    dashboard,
    recruiters,
    slots,
    system,
    templates,
    questions,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    register_template_globals()
    integration: BotIntegration = setup_bot_state(app)
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    logging.warning("ROUTES LOADED: %s", routes)
    try:
        yield
    finally:
        await integration.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="TG Bot Admin UI", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(system.router)
    app.include_router(dashboard.router)
    app.include_router(slots.router)
    app.include_router(recruiters.router)
    app.include_router(cities.router)
    app.include_router(templates.router)
    app.include_router(questions.router)
    app.include_router(api.router)

    return app


app = create_app()

__all__ = ["app", "create_app", "lifespan"]
