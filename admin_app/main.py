"""Compatibility shim for the legacy import path `admin_app.main`."""

from backend.apps.admin_api.main import app, create_app, lifespan  # noqa: F401

__all__ = ["app", "create_app", "lifespan"]
