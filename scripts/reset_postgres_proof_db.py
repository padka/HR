#!/usr/bin/env python3
"""Reset the disposable PostgreSQL proof database schema before proof tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ALLOWED_HOSTS = {"localhost", "127.0.0.1", None}


def _strip_async_driver(database_url: str) -> str:
    if "+asyncpg" in database_url:
        return database_url.replace("+asyncpg", "", 1)
    return database_url


def _is_disposable_database_name(database_name: str) -> bool:
    lowered = (database_name or "").strip().lower()
    return lowered.endswith("_test") or lowered.endswith("_proof") or "_test_" in lowered


def validate_reset_target(database_url: str) -> str:
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for PostgreSQL proof reset")

    parsed = make_url(_strip_async_driver(database_url))
    database_name = parsed.database or ""

    if not parsed.drivername.startswith("postgresql"):
        raise RuntimeError("PostgreSQL proof reset only supports postgresql URLs")
    if parsed.host not in ALLOWED_HOSTS:
        raise RuntimeError(f"Refusing PostgreSQL proof reset for non-local host: {parsed.host!r}")
    if not _is_disposable_database_name(database_name):
        raise RuntimeError(
            "Refusing PostgreSQL proof reset for non-disposable database "
            f"name: {database_name!r}"
        )

    return _strip_async_driver(database_url)


def reset_public_schema(database_url: str) -> None:
    sync_url = validate_reset_target(database_url)
    with psycopg.connect(sync_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cur.execute("CREATE SCHEMA public AUTHORIZATION CURRENT_USER")
            cur.execute("GRANT USAGE ON SCHEMA public TO PUBLIC")


def main() -> int:
    database_url = (
        os.environ.get("PG_PROOF_DATABASE_URL", "").strip()
        or os.environ.get("TEST_DATABASE_URL", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
    )
    try:
        reset_public_schema(database_url)
    except Exception as exc:
        print(f"PostgreSQL proof reset failed: {exc}", file=sys.stderr)
        return 1

    print("PostgreSQL proof database public schema reset complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
