"""Admin API application exports."""

from .main import app, create_app  # noqa: F401

__all__ = ["app", "create_app"]
