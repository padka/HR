#!/usr/bin/env python3
"""Run pytest in CI with bounded runtime and GitHub-visible diagnostics."""

from __future__ import annotations

import argparse
import faulthandler
import os
from pathlib import Path
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET

import pytest

DEFAULT_JUNIT_PATH = ".pytest-ci-results.xml"
SENSITIVE_RE = re.compile(
    r"\b(client_secret|access_token|refresh_token|poll_token|token|code|state)"
    r"(\s*[=:]\s*)([^\s&]+)",
    re.IGNORECASE,
)


def _redact(value: str) -> str:
    return SENSITIVE_RE.sub(r"\1\2REDACTED", value)


def _gha_escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _emit_error(title: str, message: str) -> None:
    safe_message = _gha_escape(_redact(message[:8000]))
    safe_title = _gha_escape(_redact(title))
    print(f"::error title={safe_title}::{safe_message}", flush=True)


def _first_junit_failure(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return f"Could not parse pytest JUnit report {path}: {exc}"

    for case in root.iter("testcase"):
        for child in case:
            if child.tag not in {"failure", "error"}:
                continue
            classname = case.attrib.get("classname", "")
            name = case.attrib.get("name", "")
            message = child.attrib.get("message", "")
            body = (child.text or "").strip()
            label = "::".join(part for part in (classname, name) if part)
            details = "\n".join(part for part in (label, message, body) if part)
            return details or "pytest reported a failure without details"
    return None


def _start_watchdog(timeout_seconds: int) -> None:
    if timeout_seconds <= 0:
        return

    def _watch() -> None:
        time.sleep(timeout_seconds)
        _emit_error(
            "Backend tests timeout",
            f"pytest exceeded {timeout_seconds} seconds; dumping Python stack traces",
        )
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        os._exit(124)

    threading.Thread(target=_watch, name="pytest-timeout-watchdog", daemon=True).start()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(os.getenv("BACKEND_TEST_TIMEOUT_SECONDS", "1800")),
        help="Maximum pytest runtime before stack dump and exit.",
    )
    parser.add_argument(
        "--junit-path",
        default=os.getenv("PYTEST_JUNIT_PATH", DEFAULT_JUNIT_PATH),
        help="Path for pytest JUnit output used for CI annotations.",
    )
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.pytest_args[:1] == ["--"]:
        args.pytest_args = args.pytest_args[1:]
    if not args.pytest_args:
        parser.error("pytest arguments are required after --")
    return args


def main() -> int:
    args = _parse_args()
    junit_path = Path(args.junit_path)
    pytest_args = list(args.pytest_args)
    if not any(arg == "--junitxml" or arg.startswith("--junitxml=") for arg in pytest_args):
        pytest_args.insert(0, f"--junitxml={junit_path}")

    faulthandler.enable(all_threads=True)
    _start_watchdog(args.timeout_seconds)
    status = int(pytest.main(pytest_args))
    if status:
        failure = _first_junit_failure(junit_path)
        _emit_error("Backend tests failed", failure or f"pytest exited with status {status}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
