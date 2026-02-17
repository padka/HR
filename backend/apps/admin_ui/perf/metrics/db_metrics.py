"""Backward-compatible import shim for DB metrics instrumentation.

New code should import from:
`backend.apps.admin_ui.perf.metrics.db`.
"""

from __future__ import annotations

from backend.apps.admin_ui.perf.metrics.db import (
    install_sqlalchemy_metrics,
    start_db_stats_task,
    start_sql_profile_task,
)

__all__ = ["install_sqlalchemy_metrics", "start_db_stats_task", "start_sql_profile_task"]
