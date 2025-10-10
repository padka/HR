from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.core.bootstrap import ensure_database_ready
from backend.core.db import async_engine
from backend.apps.admin_api.admin import mount_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_database_ready()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="TG Bot Admin API", lifespan=lifespan)
    mount_admin(app, async_engine)

    @app.get("/")
    async def root():
        return {"ok": True, "admin": "/admin"}

    return app


app = create_app()
