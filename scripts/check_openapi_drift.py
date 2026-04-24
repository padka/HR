#!/usr/bin/env python3
"""Check tracked OpenAPI schemas against the live FastAPI apps."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_export_openapi = __import__(
    "scripts.export_openapi",
    fromlist=["TARGETS", "build_live_schema"],
)
TARGETS = _export_openapi.TARGETS
build_live_schema = _export_openapi.build_live_schema
normalize_openapi_schema = _export_openapi.normalize_openapi_schema

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


def _report_schema_drift(*, target_name: str, committed_schema: dict, live_schema: dict) -> bool:
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
            f"✅ {target_name}: OpenAPI schema in sync "
            f"({len(live_paths)} paths, {len(live_operations)} operations)"
        )
        return False

    print(f"❌ {target_name}: OpenAPI drift detected!")

    if missing_paths:
        print(f"\n  Missing paths ({len(missing_paths)}):")
        for path in sorted(missing_paths)[:20]:
            print(f"    - {path}")
        if len(missing_paths) > 20:
            print(f"    ... and {len(missing_paths) - 20} more")

    if stale_paths:
        print(f"\n  Stale paths ({len(stale_paths)}):")
        for path in sorted(stale_paths)[:20]:
            print(f"    - {path}")
        if len(stale_paths) > 20:
            print(f"    ... and {len(stale_paths) - 20} more")

    if missing_operations:
        print(f"\n  Missing operations ({len(missing_operations)}):")
        for method, path in sorted(missing_operations)[:20]:
            print(f"    - {method} {path}")
        if len(missing_operations) > 20:
            print(f"    ... and {len(missing_operations) - 20} more")

    if stale_operations:
        print(f"\n  Stale operations ({len(stale_operations)}):")
        for method, path in sorted(stale_operations)[:20]:
            print(f"    - {method} {path}")
        if len(stale_operations) > 20:
            print(f"    ... and {len(stale_operations) - 20} more")

    if not missing_operations and not stale_operations and not schemas_match:
        print("\n  Operation sets match, but schema payload still differs.")

    return True


def main() -> int:
    os.environ["RECRUITSMART_OPENAPI_MODE"] = "1"
    drift_found = False

    for target in TARGETS:
        try:
            live_schema = build_live_schema(target.name)
        except Exception as exc:
            print(f"❌ {target.name}: failed to build live OpenAPI schema: {exc}")
            print("OpenAPI drift check failed closed because the live app is not importable.")
            return 1

        committed_schema = normalize_openapi_schema(json.loads(target.path.read_text(encoding="utf-8")))
        drift_found |= _report_schema_drift(
            target_name=target.name,
            committed_schema=committed_schema,
            live_schema=live_schema,
        )

    if not drift_found:
        return 0

    print(
        "\n  Run: make openapi-export "
        "(this refreshes admin_ui/admin_api tracked schemas and frontend/app/src/api/schema.ts)"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
