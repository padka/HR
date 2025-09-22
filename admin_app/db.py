"""Compatibility layer pointing to the new backend core DB helpers."""

from backend.core.db import (
    async_engine as engine,
    async_session as SessionLocal,
    init_models as init_db,
    new_async_session,
)

__all__ = ["engine", "SessionLocal", "init_db", "new_async_session"]
