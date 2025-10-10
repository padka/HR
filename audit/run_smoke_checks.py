#!/usr/bin/env python3
"""Run smoke checks against the admin UI FastAPI app."""
from __future__ import annotations

import argparse
import asyncio
import importlib
import os
from typing import List, Tuple

from fastapi.testclient import TestClient

TARGET_PATHS: List[Tuple[str, str]] = [
    ("dashboard", "/"),
    ("recruiters", "/recruiters"),
    ("questions", "/questions"),
    ("templates", "/templates"),
    ("slots", "/slots"),
]


async def ensure_db_ready() -> None:
    from backend.core.bootstrap import ensure_database_ready

    await ensure_database_ready()


def make_client(skip_bootstrap: bool) -> TestClient:
    module = importlib.import_module("backend.apps.admin_ui.app")
    if skip_bootstrap:
        async def _noop() -> None:  # pragma: no cover - diagnostic helper
            return None

        module.ensure_database_ready = _noop  # type: ignore[attr-defined]
    app = module.create_app()
    return TestClient(app)


def run_checks(skip_bootstrap: bool) -> List[Tuple[str, str, int | None, str]]:
    results: List[Tuple[str, str, int | None, str]] = []
    auth = ("test-admin", "test-admin-password")
    try:
        with make_client(skip_bootstrap) as client:
            for name, path in TARGET_PATHS:
                try:
                    response = client.get(path, auth=auth)
                    status = response.status_code
                    snippet = response.text[:200].replace("\n", " ").strip()
                except Exception as exc:  # pragma: no cover - diagnostic output
                    status = None
                    snippet = f"{type(exc).__name__}: {exc}"
                results.append((name, path, status, snippet))
    except Exception as exc:
        results.append(("startup", "<lifespan>", None, f"{type(exc).__name__}: {exc}"))
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-db", action="store_true", help="Initialise the database before running")
    args = parser.parse_args()

    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")
    os.environ.setdefault("ADMIN_USER", "test-admin")
    os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
    os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
    os.environ.setdefault("BOT_ENABLED", "0")
    os.environ.setdefault("BOT_INTEGRATION_ENABLED", "0")

    if args.with_db:
        asyncio.run(ensure_db_ready())
        skip_bootstrap = False
    else:
        skip_bootstrap = True

    results = run_checks(skip_bootstrap)
    mode = "WITH_DB" if args.with_db else "NO_DB"
    print(f"SMOKE RESULTS [{mode}]")
    for name, path, status, snippet in results:
        label = status if status is not None else "EXCEPTION"
        print(f"- {name}: {path} → {label}")
        if status is None or status >= 400:
            print(f"  detail: {snippet}")


if __name__ == "__main__":
    main()
