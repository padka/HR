"""Compatibility package for the legacy `admin_server` import path."""

from backend.apps.admin_ui.app import app, create_app, lifespan  # noqa: F401

__all__ = ["app", "create_app", "lifespan"]
