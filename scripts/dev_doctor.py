#!/usr/bin/env python3
"""Developer environment preflight checks."""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import sys
from dataclasses import dataclass
from typing import List


PYTHON_MINIMUM = (3, 11)
PYTHON_TARGET = (3, 12)
MODULE_REQUIREMENTS = {
    "fastapi": "fastapi==0.112.0",
    "starlette": "starlette==0.37.2",
    "uvicorn": "uvicorn[standard]==0.30.6",
    "itsdangerous": "itsdangerous==2.2.0",
    "jinja2": "Jinja2==3.1.4",
    "aiosqlite": "aiosqlite==0.20.0",
    "sqlalchemy": "SQLAlchemy[asyncio]==2.0.32",
    "pydantic": "pydantic==2.8.2",
}


@dataclass
class CheckResult:
    label: str
    status: str
    detail: str
    hint: str = ""

    def is_failure(self) -> bool:
        return self.status == "FAIL"


def format_status(status: str) -> str:
    return f"[{status:>4}]"


def _fmt_version(version: tuple[int, int]) -> str:
    return ".".join(map(str, version))


def check_python() -> CheckResult:
    current = sys.version_info
    detected = f"{current.major}.{current.minor}.{current.micro}"
    if current >= PYTHON_TARGET:
        return CheckResult(
            label="Python runtime",
            status="OK",
            detail=f"Detected Python {detected}",
        )
    if current >= PYTHON_MINIMUM:
        target = _fmt_version(PYTHON_TARGET)
        return CheckResult(
            label="Python runtime",
            status="WARN",
            detail=f"Detected Python {detected}",
            hint=(
                "Upgrade to Python "
                f"{target} for full support; 3.11 remains temporarily allowed."
            ),
        )
    minimum = _fmt_version(PYTHON_MINIMUM)
    return CheckResult(
        label="Python runtime",
        status="FAIL",
        detail=f"Detected Python {detected}",
        hint=(
            f"Use Python {minimum} or newer (prefer {_fmt_version(PYTHON_TARGET)})."
        ),
    )


def _dist_name(spec: str) -> str:
    base = spec.split("==", 1)[0]
    return base.split("[", 1)[0]


def check_module(name: str, spec: str) -> CheckResult:
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as exc:
        return CheckResult(
            label=f"Import {name}",
            status="FAIL",
            detail=f"{exc}",
            hint=f"Install with `pip install {spec}`.",
        )
    try:
        version = importlib.metadata.version(_dist_name(spec))
    except importlib.metadata.PackageNotFoundError:
        version = getattr(module, "__version__", None)
    detail = f"Found {name} {version}" if version else f"Found {name}"
    return CheckResult(label=f"Import {name}", status="OK", detail=detail)


def check_session_secret() -> CheckResult:
    secret = (
        os.getenv("SESSION_SECRET_KEY")
        or os.getenv("SESSION_SECRET")
        or os.getenv("SECRET_KEY")
    )
    if secret:
        return CheckResult(
            label="Session secret",
            status="OK",
            detail="SESSION_SECRET_KEY detected.",
        )
    return CheckResult(
        label="Session secret",
        status="WARN",
        detail="SESSION_SECRET_KEY not set.",
        hint="Create a dev secret, e.g. `export SESSION_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')`.",
    )


def run_checks() -> List[CheckResult]:
    results: List[CheckResult] = [check_python()]
    for module, spec in MODULE_REQUIREMENTS.items():
        results.append(check_module(module, spec))
    results.append(check_session_secret())
    return results


def main() -> int:
    results = run_checks()
    failures = False
    warnings = False
    print("Dev environment preflight:\n")
    for result in results:
        print(f"{format_status(result.status)} {result.label}: {result.detail}")
        if result.hint:
            print(f"       → {result.hint}")
        if result.status == "FAIL":
            failures = True
        elif result.status == "WARN":
            warnings = True

    if failures:
        print("\nResolve FAIL items above and re-run `make doctor`.")
        return 1
    if warnings:
        print("\nWarnings detected; review the hints above before running the app.")
    else:
        print("\nAll checks passed. You're good to go! 🚀")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
