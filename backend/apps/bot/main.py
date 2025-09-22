"""Compatibility wrapper delegating to top-level bot module."""

from bot import bot, dp, main  # noqa: F401

__all__ = ["bot", "dp", "main"]
