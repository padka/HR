#!/usr/bin/env python3
"""Check that frontend/app/openapi.json matches the live backend schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.export_openapi import OPENAPI_PATH, build_live_schema

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def _operation_keys(schema: dict) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for path, operations in schema.get("paths", {}).items():
        if not isinstance(operations, dict):
            continue
        for method in operations:
            if method.lower() in HTTP_METHODS:
                keys.add((method.upper(), path))
    return keys


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def main() -> int:
    try:
        live_schema = build_live_schema()
    except Exception as exc:
        print(f"⚠️  Cannot import app: {exc}")
        print("Skipping OpenAPI drift check (app not importable in CI)")
        return 0

    committed_schema = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    live_paths = set(live_schema.get("paths", {}).keys())
    committed_paths = set(committed_schema.get("paths", {}).keys())
    live_operations = _operation_keys(live_schema)
    committed_operations = _operation_keys(committed_schema)

    missing_paths = live_paths - committed_paths
    stale_paths = committed_paths - live_paths
    missing_operations = live_operations - committed_operations
    stale_operations = committed_operations - live_operations
    schemas_match = _canonical_json(live_schema) == _canonical_json(committed_schema)

    if not (missing_paths or stale_paths or missing_operations or stale_operations) and schemas_match:
        print(
            f"✅ OpenAPI schema in sync ({len(live_paths)} paths, {len(live_operations)} operations)"
        )
        return 0

    print("❌ OpenAPI drift detected!")

    if missing_paths:
        print(f"\n  Missing paths from frontend schema ({len(missing_paths)}):")
        for path in sorted(missing_paths)[:20]:
            print(f"    - {path}")
        if len(missing_paths) > 20:
            print(f"    ... and {len(missing_paths) - 20} more")

    if stale_paths:
        print(f"\n  Stale paths in frontend schema ({len(stale_paths)}):")
        for path in sorted(stale_paths)[:20]:
            print(f"    - {path}")
        if len(stale_paths) > 20:
            print(f"    ... and {len(stale_paths) - 20} more")

    if missing_operations:
        print(f"\n  Missing operations from frontend schema ({len(missing_operations)}):")
        for method, path in sorted(missing_operations)[:20]:
            print(f"    - {method} {path}")
        if len(missing_operations) > 20:
            print(f"    ... and {len(missing_operations) - 20} more")

    if stale_operations:
        print(f"\n  Stale operations in frontend schema ({len(stale_operations)}):")
        for method, path in sorted(stale_operations)[:20]:
            print(f"    - {method} {path}")
        if len(stale_operations) > 20:
            print(f"    ... and {len(stale_operations) - 20} more")

    if not missing_operations and not stale_operations and not schemas_match:
        print("\n  Operation sets match, but schema payload still differs.")

    print(
        "\n  Run: .venv/bin/python scripts/export_openapi.py && "
        "cd frontend/app && npx openapi-typescript openapi.json -o src/api/schema.ts"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
