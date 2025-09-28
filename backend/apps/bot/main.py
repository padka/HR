"""Compatibility module re-exporting bot startup helpers."""

from __future__ import annotations

from .app import create_application, main

__all__ = ["create_application", "main"]
