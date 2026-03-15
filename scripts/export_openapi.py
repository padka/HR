#!/usr/bin/env python3
"""Export the live backend OpenAPI schema for the frontend typed client."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = REPO_ROOT / "frontend" / "app" / "openapi.json"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _bootstrap_openapi_env() -> None:
    """Force a self-contained test environment for schema generation."""
    runtime_dir = Path(tempfile.gettempdir()) / "recruitsmart_openapi_runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log_dir = runtime_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    os.environ["ENVIRONMENT"] = "test"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{runtime_dir / 'openapi.db'}"
    os.environ["DATA_DIR"] = str(runtime_dir)
    os.environ["LOG_FILE"] = str(log_dir / "openapi.log")
    os.environ["SESSION_SECRET"] = "openapi-test-session-secret-0123456789abcdef"
    os.environ.setdefault("ADMIN_PASSWORD", "openapi-test-admin-password")
    os.environ["NOTIFICATION_BROKER"] = "memory"
    os.environ["BOT_ENABLED"] = "false"
    os.environ["BOT_INTEGRATION_ENABLED"] = "false"
    os.environ["MAX_BOT_ENABLED"] = "false"
    os.environ["AI_ENABLED"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "false"


def build_live_schema() -> dict:
    _bootstrap_openapi_env()
    from backend.apps.admin_ui.app import create_app

    app = create_app()
    return app.openapi()


def write_openapi_schema(path: Path = OPENAPI_PATH) -> tuple[Path, dict]:
    schema = build_live_schema()
    path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path, schema


def main() -> int:
    path, schema = write_openapi_schema()
    print(f"Exported OpenAPI schema to {path} ({len(schema.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
