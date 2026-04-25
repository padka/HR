#!/usr/bin/env python3
"""Preflight checks for bounded live contours before a service restart."""

from __future__ import annotations

import argparse
import importlib
import sys
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = PROJECT_ROOT / "deploy" / "contours"
REQUIRED_IMPORTS = {
    "admin": [
        "backend.apps.admin_ui.app",
        "backend.apps.admin_ui.routers.api_misc",
        "backend.apps.admin_ui.services.candidates.helpers",
    ],
    "maxpilot": [
        "backend.apps.admin_api.main",
        "backend.apps.admin_api.max_launch",
        "backend.apps.admin_api.candidate_access.router",
    ],
}
EXPECTED_REVISIONS = {
    "admin": "0105_unique_users_max_user_id",
    "maxpilot": "0105_unique_users_max_user_id",
}


def _load_manifest(contour: str) -> list[str]:
    manifest_file = MANIFEST_DIR / f"{contour}.txt"
    if not manifest_file.exists():
        raise SystemExit(f"Manifest not found: {manifest_file}")
    lines = []
    for raw_line in manifest_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    if not lines:
        raise SystemExit(f"Manifest is empty: {manifest_file}")
    return lines


def _check_manifest_paths(root: Path, manifest_paths: list[str]) -> list[str]:
    problems: list[str] = []
    for relative_path in manifest_paths:
        target = root / relative_path
        if not target.exists():
            problems.append(f"missing path: {target}")
    return problems


def _check_expected_revision(root: Path, contour: str) -> list[str]:
    expected_revision = EXPECTED_REVISIONS.get(contour)
    if not expected_revision:
        return []
    revision_matches = list((root / "backend" / "migrations" / "versions").glob(f"*{expected_revision}*.py"))
    if revision_matches:
        return []
    return [f"missing migration revision file: {expected_revision}"]


def _check_imports(root: Path, contour: str) -> list[str]:
    problems: list[str] = []
    sys.path.insert(0, str(root))
    warnings.filterwarnings(
        "ignore",
        message="'crypt' is deprecated and slated for removal in Python 3.13",
        category=DeprecationWarning,
    )
    try:
        for module_name in REQUIRED_IMPORTS[contour]:
            try:
                importlib.import_module(module_name)
            except Exception as exc:  # noqa: BLE001 - preflight needs exact import failures
                problems.append(f"import failed: {module_name}: {exc}")
    finally:
        try:
            sys.path.remove(str(root))
        except ValueError:
            pass
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contour", choices=sorted(REQUIRED_IMPORTS), required=True)
    parser.add_argument("--root", default=".", help="Contour root to validate")
    args = parser.parse_args()

    contour_root = Path(args.root).resolve()
    manifest_paths = _load_manifest(args.contour)
    problems = []
    problems.extend(_check_manifest_paths(contour_root, manifest_paths))
    problems.extend(_check_expected_revision(contour_root, args.contour))
    problems.extend(_check_imports(contour_root, args.contour))

    if problems:
        print("Contour preflight failed:\n")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print(f"Contour preflight passed for {args.contour}: {contour_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
