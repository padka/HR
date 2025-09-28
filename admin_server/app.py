"""Compatibility shim that re-exports the actual admin UI FastAPI app."""

from backend.apps.admin_ui.app import app, create_app, lifespan

__all__ = ["app", "create_app", "lifespan"]
