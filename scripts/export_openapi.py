#!/usr/bin/env python3
"""Export tracked OpenAPI schemas from the live FastAPI apps."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ADMIN_UI_OPENAPI_PATH = REPO_ROOT / "frontend" / "app" / "openapi.json"
ADMIN_API_OPENAPI_PATH = REPO_ROOT / "backend" / "apps" / "admin_api" / "openapi.json"
OPENAPI_MODE_ENV = "RECRUITSMART_OPENAPI_MODE"
_QUIET_PYDANTIC_WARNING = (
    r'Field "model_custom_emoji_id" has conflict with protected namespace "model_"\.'
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True)
class OpenAPITarget:
    name: str
    path: Path
    importer: str


TARGETS: tuple[OpenAPITarget, ...] = (
    OpenAPITarget(
        name="admin_ui",
        path=ADMIN_UI_OPENAPI_PATH,
        importer="backend.apps.admin_ui.app:create_app",
    ),
    OpenAPITarget(
        name="admin_api",
        path=ADMIN_API_OPENAPI_PATH,
        importer="backend.apps.admin_api.main:create_app",
    ),
)


def _bootstrap_openapi_env() -> None:
    """Force a self-contained environment for schema generation."""
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
    os.environ["REDIS_URL"] = ""
    os.environ["REDIS_NOTIFICATIONS_URL"] = ""
    os.environ["BOT_ENABLED"] = "false"
    os.environ["BOT_INTEGRATION_ENABLED"] = "false"
    os.environ["MAX_BOT_ENABLED"] = "false"
    os.environ["AI_ENABLED"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ[OPENAPI_MODE_ENV] = "1"


@contextmanager
def _openapi_quiet_context():
    """Suppress known non-actionable OpenAPI-mode noise while keeping real failures visible."""

    previous_disable_level = logging.root.manager.disable
    logging.disable(logging.INFO)
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=_QUIET_PYDANTIC_WARNING,
                category=UserWarning,
                module=r"pydantic\._internal\._fields",
            )
            yield
    finally:
        logging.disable(previous_disable_level)


def _target_by_name(name: str) -> OpenAPITarget:
    for target in TARGETS:
        if target.name == name:
            return target
    known = ", ".join(target.name for target in TARGETS)
    raise ValueError(f"Unknown OpenAPI target '{name}'. Expected one of: {known}")


def _load_app_factory(target: OpenAPITarget):
    module_name, factory_name = target.importer.split(":", 1)
    module = __import__(module_name, fromlist=[factory_name])
    return getattr(module, factory_name)


def build_live_schema(target: str = "admin_ui") -> dict:
    _bootstrap_openapi_env()
    spec = _target_by_name(target)
    with _openapi_quiet_context():
        create_app = _load_app_factory(spec)
        app = create_app()
        return normalize_openapi_schema(app.openapi())


def normalize_openapi_schema(value):
    """Normalize semantically equivalent FastAPI/Pydantic schema noise.

    Python/FastAPI/Pydantic combinations can differ on whether an unrestricted
    object explicitly renders ``additionalProperties: true`` and whether form
    body references are wrapped in a single-item ``allOf``. Both forms describe
    the same contract, so generated artifacts and drift checks should not depend
    on the interpreter version used by CI.
    """

    if isinstance(value, list):
        return [normalize_openapi_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    normalized = {key: normalize_openapi_schema(item) for key, item in value.items()}
    if normalized.get("type") == "object" and normalized.get("additionalProperties") is True:
        normalized.pop("additionalProperties")

    all_of = normalized.get("allOf")
    if (
        isinstance(all_of, list)
        and len(all_of) == 1
        and isinstance(all_of[0], dict)
        and set(all_of[0]) == {"$ref"}
        and set(normalized).issubset({"allOf", "title"})
    ):
        return dict(all_of[0])

    return normalized


def write_openapi_schema(target: str = "admin_ui", path: Path | None = None) -> tuple[Path, dict]:
    spec = _target_by_name(target)
    output_path = path or spec.path
    schema = build_live_schema(target)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path, schema


def export_all_schemas() -> list[tuple[str, Path, dict]]:
    exported: list[tuple[str, Path, dict]] = []
    for target in TARGETS:
        path, schema = write_openapi_schema(target.name)
        exported.append((target.name, path, schema))
    return exported


def main() -> int:
    for target, path, schema in export_all_schemas():
        print(f"Exported {target} OpenAPI schema to {path} ({len(schema.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
