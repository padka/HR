"""Backward-compatible import shim for HTTP metrics middleware.

New code should import from:
`backend.apps.admin_ui.perf.metrics.http`.
"""

from __future__ import annotations

from backend.apps.admin_ui.perf.metrics.http import HTTPMetricsMiddleware

__all__ = ["HTTPMetricsMiddleware"]

