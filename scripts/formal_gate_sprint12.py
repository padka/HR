#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_PENDING = "manual_pending"


def ensure_runtime_python() -> None:
    try:
        import fastapi  # noqa: F401

        return
    except Exception:
        root = Path(__file__).resolve().parents[1]
        venv_python = root / ".venv" / "bin" / "python"
        if not venv_python.exists():
            return
        if Path(sys.executable).resolve() == venv_python.resolve():
            return
        os.execv(str(venv_python), [str(venv_python), *sys.argv])


@dataclass
class CommandSpec:
    check_id: str
    title: str
    argv: list[str]
    cwd: Path
    timeout_sec: int = 1800


@dataclass
class CommandResult:
    check_id: str
    title: str
    command: str
    cwd: str
    status: str
    return_code: int
    duration_sec: float
    log_file: str
    summary: str


@contextmanager
def temporary_env(overrides: dict[str, str | None]):
    original: dict[str, str | None] = {}
    for key, value in overrides.items():
        original[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _tail_summary(text: str, *, lines: int = 8) -> str:
    chunks = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not chunks:
        return ""
    return " | ".join(chunks[-lines:])


def run_command(spec: CommandSpec, logs_dir: Path) -> CommandResult:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{spec.check_id}.log"
    started = time.perf_counter()
    command = shlex.join(spec.argv)
    try:
        proc = subprocess.run(
            spec.argv,
            cwd=spec.cwd,
            capture_output=True,
            text=True,
            timeout=spec.timeout_sec,
            check=False,
        )
        output = (proc.stdout or "") + ("\n" if proc.stdout and proc.stderr else "") + (proc.stderr or "")
        log_file.write_text(output, encoding="utf-8")
        duration = time.perf_counter() - started
        status = STATUS_PASS if proc.returncode == 0 else STATUS_FAIL
        summary = _tail_summary(output) or f"exit code {proc.returncode}"
        return CommandResult(
            check_id=spec.check_id,
            title=spec.title,
            command=command,
            cwd=str(spec.cwd),
            status=status,
            return_code=proc.returncode,
            duration_sec=duration,
            log_file=str(log_file),
            summary=summary,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - started
        output = (exc.stdout or "") + ("\n" if exc.stdout and exc.stderr else "") + (exc.stderr or "")
        log_file.write_text(output, encoding="utf-8")
        return CommandResult(
            check_id=spec.check_id,
            title=spec.title,
            command=command,
            cwd=str(spec.cwd),
            status=STATUS_FAIL,
            return_code=124,
            duration_sec=duration,
            log_file=str(log_file),
            summary=f"timeout after {spec.timeout_sec}s",
        )
    except FileNotFoundError as exc:
        duration = time.perf_counter() - started
        log_file.write_text(str(exc), encoding="utf-8")
        return CommandResult(
            check_id=spec.check_id,
            title=spec.title,
            command=command,
            cwd=str(spec.cwd),
            status=STATUS_FAIL,
            return_code=127,
            duration_sec=duration,
            log_file=str(log_file),
            summary=str(exc),
        )


def build_inventory(root: Path, out_dir: Path) -> dict[str, Any]:
    venv_pytest = root / ".venv" / "bin" / "pytest"
    db_tmp = Path(tempfile.gettempdir()) / f"recruitsmart_gate_routes_{os.getpid()}.db"
    data_dir = root / ".tmp" / "gate-data"
    data_dir.mkdir(parents=True, exist_ok=True)

    base_env = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_tmp}",
        "DATA_DIR": str(data_dir),
        "ADMIN_USER": "gate_admin",
        "ADMIN_PASSWORD": "gate_admin_password",
        "SESSION_SECRET": "gate-session-secret-0123456789abcdef0123456789abcd",
        "BOT_CALLBACK_SECRET": "gate-bot-callback-secret-0123456789abcdef012345",
        "ALLOW_DEV_AUTOADMIN": "0",
        "ALLOW_LEGACY_BASIC": "0",
        "RATE_LIMIT_ENABLED": "0",
    }

    def _collect(enable_legacy: bool) -> dict[str, Any]:
        with temporary_env(
            {
                **base_env,
                "ENABLE_LEGACY_ASSIGNMENTS_API": "1" if enable_legacy else "0",
            }
        ):
            from backend.core import settings as settings_module

            settings_module.get_settings.cache_clear()
            from backend.apps.admin_ui.app import create_app

            app = create_app()
            routes: list[dict[str, Any]] = []
            for route in app.routes:
                route_type = route.__class__.__name__
                if route_type == "APIRoute":
                    methods = sorted(m for m in route.methods if m not in {"HEAD", "OPTIONS"})
                    dep_names = sorted(
                        {
                            getattr(dep.call, "__name__", str(dep.call))
                            for dep in route.dependant.dependencies
                        }
                    )
                    guard = "none"
                    if "require_admin" in dep_names:
                        guard = "require_admin"
                    elif "require_principal" in dep_names:
                        guard = "require_principal"
                    routes.append(
                        {
                            "kind": "http",
                            "path": route.path,
                            "methods": methods,
                            "guard": guard,
                            "deps": dep_names,
                        }
                    )
                elif route_type == "APIWebSocketRoute":
                    routes.append(
                        {
                            "kind": "ws",
                            "path": route.path,
                            "methods": ["WS"],
                            "guard": "handler",
                            "deps": [],
                        }
                    )
            return {"routes": routes}

    default_view = _collect(enable_legacy=False)
    legacy_view = _collect(enable_legacy=True)

    public_exact = {
        "/api/health",
        "/api/csrf",
    }
    public_prefixes = (
        "/auth/",
        "/api/webapp/",
    )

    sensitive_prefixes = (
        "/api/",
        "/dashboard",
        "/slots",
        "/cities",
        "/candidates",
        "/profile",
        "/recruiters",
        "/workflow",
        "/detailization",
        "/ai",
        "/knowledge-base",
        "/simulator",
    )

    sensitive_rows: list[dict[str, Any]] = []
    findings: list[str] = []

    for route in default_view["routes"]:
        if route["kind"] != "http":
            continue
        path = route["path"]
        is_public = path in public_exact or any(path.startswith(prefix) for prefix in public_prefixes)
        is_sensitive = path == "/metrics" or any(path.startswith(prefix) for prefix in sensitive_prefixes)
        if not is_sensitive or is_public:
            continue

        token_guard_exceptions = {
            "/api/slot-assignments/{assignment_id}/confirm",
            "/api/slot-assignments/{assignment_id}/request-reschedule",
            "/api/slot-assignments/{assignment_id}/decline",
        }
        special_handler_guard = path == "/metrics" or path in token_guard_exceptions
        guarded = route["guard"] in {"require_principal", "require_admin"} or special_handler_guard
        row = {
            "path": path,
            "methods": ",".join(route["methods"]),
            "guard": (
                route["guard"]
                if not special_handler_guard
                else ("token_guard" if path in token_guard_exceptions else "handler_guard")
            ),
            "status": STATUS_PASS if guarded else STATUS_FAIL,
        }
        sensitive_rows.append(row)
        if not guarded:
            findings.append(f"unguarded_sensitive_route:{path}:{row['methods']}")

    default_legacy_routes = [
        route
        for route in default_view["routes"]
        if route["kind"] == "http" and route["path"].startswith("/api/v1/assignments")
    ]
    if default_legacy_routes:
        findings.append("legacy_assignments_routes_present_by_default")

    enabled_legacy_routes = [
        route
        for route in legacy_view["routes"]
        if route["kind"] == "http" and route["path"].startswith("/api/v1/assignments")
    ]
    if not enabled_legacy_routes:
        findings.append("legacy_assignments_routes_missing_when_enabled")
    else:
        for route in enabled_legacy_routes:
            if route["guard"] not in {"require_principal", "require_admin"}:
                findings.append(f"legacy_assignments_route_unguarded:{route['path']}")

    ws_calendar_exists = any(
        route["kind"] == "ws" and route["path"] == "/ws/calendar"
        for route in default_view["routes"]
    )
    if not ws_calendar_exists:
        findings.append("ws_calendar_route_missing")

    inventory_markdown = out_dir / "route_inventory.md"
    table_lines = [
        "# Sprint 1/2 Route Inventory",
        "",
        f"- Generated at: `{datetime.now(UTC).isoformat()}`",
        f"- Sensitive routes inspected: `{len(sensitive_rows)}`",
        f"- Findings: `{len(findings)}`",
        "",
        "| Path | Methods | Guard | Status |",
        "| --- | --- | --- | --- |",
    ]
    for row in sorted(sensitive_rows, key=lambda item: item["path"]):
        table_lines.append(
            f"| `{row['path']}` | `{row['methods']}` | `{row['guard']}` | `{row['status']}` |"
        )
    if not sensitive_rows:
        table_lines.append("| _none_ | - | - | - |")
    if findings:
        table_lines.extend(["", "## Findings", ""])
        for finding in findings:
            table_lines.append(f"- `{finding}`")
    inventory_markdown.write_text("\n".join(table_lines) + "\n", encoding="utf-8")

    return {
        "status": STATUS_PASS if not findings else STATUS_FAIL,
        "findings": findings,
        "sensitive_routes_total": len(sensitive_rows),
        "inventory_markdown": str(inventory_markdown),
        "legacy_default_absent": not default_legacy_routes,
        "legacy_enabled_count": len(enabled_legacy_routes),
        "ws_calendar_exists": ws_calendar_exists,
        "pytest_binary_exists": venv_pytest.exists(),
    }


def criterion_status_from_checks(check_ids: list[str], command_results: dict[str, CommandResult]) -> str:
    for check_id in check_ids:
        result = command_results.get(check_id)
        if result is None or result.status != STATUS_PASS:
            return STATUS_FAIL
    return STATUS_PASS


def aggregate_sprint_status(criteria: list[dict[str, Any]]) -> str:
    statuses = [item["status"] for item in criteria]
    if STATUS_FAIL in statuses:
        return STATUS_FAIL
    if STATUS_PENDING in statuses:
        return STATUS_PENDING
    return STATUS_PASS


def to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Formal Gate Sprint 1/2",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Overall: `{report['overall_status']}`",
        f"- Sprint 1 Gate: `{report['sprint_gate_status']['sprint1']}`",
        f"- Sprint 2 Gate: `{report['sprint_gate_status']['sprint2']}`",
        "",
        "## Criteria",
        "",
        "| ID | Sprint | Criterion | Status | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report["criteria"]:
        lines.append(
            f"| `{item['id']}` | `{item['sprint']}` | {item['criterion']} | `{item['status']}` | {item['evidence']} |"
        )

    lines.extend(
        [
            "",
            "## Automated Checks",
            "",
            "| Check | Status | Duration (s) | Command |",
            "| --- | --- | --- | --- |",
        ]
    )
    for check in report["checks"]:
        lines.append(
            f"| `{check['check_id']}` | `{check['status']}` | `{check['duration_sec']:.1f}` | `{check['command']}` |"
        )

    lines.extend(
        [
            "",
            "## Route Inventory",
            "",
            f"- Status: `{report['route_inventory']['status']}`",
            f"- Findings: `{len(report['route_inventory']['findings'])}`",
            f"- Inventory artifact: `{report['route_inventory']['inventory_markdown']}`",
            "",
            "## Manual Sign-Off",
            "",
            f"- Sprint 1 UX sign-off: `{report['manual_signoff']['sprint1_ux']}`",
            f"- Sprint 1 demo sign-off: `{report['manual_signoff']['sprint1_demo']}`",
            f"- Sprint 2 security review sign-off: `{report['manual_signoff']['sprint2_security_review']}`",
            "",
            "## Artifacts",
            "",
            f"- JSON: `{report['artifacts']['json']}`",
            f"- Markdown: `{report['artifacts']['markdown']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run formal gate for Sprint 1/2 criteria.")
    parser.add_argument(
        "--out-dir",
        default=".local/gates/sprint1_2",
        help="Directory for generated gate artifacts.",
    )
    parser.add_argument(
        "--write-doc",
        default="docs/gates/SPRINT1_2_LAST_RUN.md",
        help="Optional markdown path to mirror latest report.",
    )
    parser.add_argument(
        "--write-route-doc",
        default="docs/gates/SPRINT1_2_ROUTE_INVENTORY_LAST_RUN.md",
        help="Optional markdown path to mirror latest route inventory.",
    )
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Skip Playwright smoke/a11y/focus checks.",
    )
    parser.add_argument(
        "--manual-sprint1-ux",
        choices=[STATUS_PASS, STATUS_FAIL, STATUS_PENDING],
        default=STATUS_PENDING,
    )
    parser.add_argument(
        "--manual-sprint1-demo",
        choices=[STATUS_PASS, STATUS_FAIL, STATUS_PENDING],
        default=STATUS_PENDING,
    )
    parser.add_argument(
        "--manual-sprint2-security",
        choices=[STATUS_PASS, STATUS_FAIL, STATUS_PENDING],
        default=STATUS_PENDING,
    )
    parser.add_argument(
        "--fail-on-pending",
        action="store_true",
        help="Exit non-zero when manual sign-off is pending.",
    )
    return parser.parse_args()


def main() -> int:
    ensure_runtime_python()
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    out_dir = (root / args.out_dir).resolve()
    logs_dir = out_dir / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)

    frontend_dir = root / "frontend" / "app"
    pytest_bin = root / ".venv" / "bin" / "pytest"
    if not pytest_bin.exists():
        print("ERROR: missing pytest binary at .venv/bin/pytest", file=sys.stderr)
        return 2

    checks: list[CommandSpec] = [
        CommandSpec(
            check_id="backend_security_regression",
            title="Backend security regression tests",
            argv=[
                str(pytest_bin),
                "tests/test_admin_surface_hardening.py",
                "tests/test_calendar_hub_scope.py",
                "tests/test_perf_metrics_endpoint.py",
                "tests/test_admin_auth_no_basic_challenge.py",
                "tests/test_rate_limiting.py",
                "-q",
            ],
            cwd=root,
        ),
        CommandSpec(
            check_id="backend_crud_regression",
            title="Backend CRUD regression tests",
            argv=[
                str(pytest_bin),
                "tests/test_admin_slots_api.py",
                "tests/test_admin_candidates_service.py",
                "-q",
            ],
            cwd=root,
        ),
        CommandSpec(
            check_id="frontend_lint",
            title="Frontend lint",
            argv=["npm", "run", "lint"],
            cwd=frontend_dir,
        ),
        CommandSpec(
            check_id="frontend_typecheck",
            title="Frontend typecheck",
            argv=["npm", "run", "typecheck"],
            cwd=frontend_dir,
        ),
        CommandSpec(
            check_id="frontend_unit",
            title="Frontend unit tests",
            argv=["npm", "run", "test"],
            cwd=frontend_dir,
        ),
        CommandSpec(
            check_id="frontend_build",
            title="Frontend build (fresh dist assets for e2e)",
            argv=["npm", "run", "build"],
            cwd=frontend_dir,
        ),
    ]
    if not args.skip_e2e:
        checks.append(
            CommandSpec(
                check_id="frontend_e2e_gate",
                title="Frontend smoke+a11y+focus e2e",
                argv=[
                    "npx",
                    "playwright",
                    "test",
                    "tests/e2e/smoke.spec.ts",
                    "tests/e2e/a11y.spec.ts",
                    "tests/e2e/focus.cities.spec.ts",
                    "tests/e2e/focus.slots.spec.ts",
                    "tests/e2e/regression-flow.spec.ts",
                ],
                cwd=frontend_dir,
            )
        )

    command_results_list: list[CommandResult] = [run_command(spec, logs_dir) for spec in checks]
    command_results = {item.check_id: item for item in command_results_list}

    route_inventory = build_inventory(root, out_dir)

    criteria: list[dict[str, Any]] = []
    criteria.append(
        {
            "id": "S1-1",
            "sprint": "Sprint 1",
            "criterion": "Smoke/a11y/focus e2e green",
            "status": criterion_status_from_checks(["frontend_e2e_gate"], command_results)
            if not args.skip_e2e
            else STATUS_PENDING,
            "evidence": "frontend_e2e_gate log",
        }
    )
    criteria.append(
        {
            "id": "S1-2",
            "sprint": "Sprint 1",
            "criterion": "Core CRUD UI/API flows without blocking regressions",
            "status": criterion_status_from_checks(
                [
                    "backend_crud_regression",
                    "frontend_lint",
                    "frontend_typecheck",
                    "frontend_unit",
                    "frontend_build",
                ],
                command_results,
            ),
            "evidence": "backend_crud_regression + frontend checks",
        }
    )
    criteria.append(
        {
            "id": "S1-3",
            "sprint": "Sprint 1",
            "criterion": "No P1 UX defects in slots/cities/candidates",
            "status": args.manual_sprint1_ux,
            "evidence": "manual QA sign-off",
        }
    )
    criteria.append(
        {
            "id": "S1-4",
            "sprint": "Sprint 1",
            "criterion": "Live demo gate: city -> slot -> candidate",
            "status": args.manual_sprint1_demo,
            "evidence": "demo protocol sign-off",
        }
    )
    criteria.append(
        {
            "id": "S2-1",
            "sprint": "Sprint 2",
            "criterion": "Unauthorized access to closed endpoints returns 401/403",
            "status": criterion_status_from_checks(["backend_security_regression"], command_results),
            "evidence": "backend_security_regression",
        }
    )
    criteria.append(
        {
            "id": "S2-2",
            "sprint": "Sprint 2",
            "criterion": "Security regression covers API and websocket",
            "status": criterion_status_from_checks(["backend_security_regression"], command_results),
            "evidence": "tests/test_admin_surface_hardening.py",
        }
    )
    criteria.append(
        {
            "id": "S2-3",
            "sprint": "Sprint 2",
            "criterion": "No critical open routes without auth in admin surface",
            "status": route_inventory["status"],
            "evidence": "route_inventory.md",
        }
    )
    criteria.append(
        {
            "id": "S2-4",
            "sprint": "Sprint 2",
            "criterion": "Internal security review sign-off",
            "status": args.manual_sprint2_security,
            "evidence": "security review record",
        }
    )

    sprint1 = [item for item in criteria if item["sprint"] == "Sprint 1"]
    sprint2 = [item for item in criteria if item["sprint"] == "Sprint 2"]
    sprint_status = {
        "sprint1": aggregate_sprint_status(sprint1),
        "sprint2": aggregate_sprint_status(sprint2),
    }

    overall = aggregate_sprint_status(criteria)
    generated_at = datetime.now(UTC).isoformat()

    report = {
        "generated_at": generated_at,
        "overall_status": overall,
        "sprint_gate_status": sprint_status,
        "checks": [item.__dict__ for item in command_results_list],
        "route_inventory": route_inventory,
        "criteria": criteria,
        "manual_signoff": {
            "sprint1_ux": args.manual_sprint1_ux,
            "sprint1_demo": args.manual_sprint1_demo,
            "sprint2_security_review": args.manual_sprint2_security,
        },
        "artifacts": {},
    }

    json_path = out_dir / "latest.json"
    md_path = out_dir / "latest.md"
    report["artifacts"]["json"] = str(json_path)
    report["artifacts"]["markdown"] = str(md_path)

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = to_markdown(report)
    md_path.write_text(markdown, encoding="utf-8")

    if args.write_doc:
        doc_path = (root / args.write_doc).resolve()
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(markdown, encoding="utf-8")

    if args.write_route_doc:
        src_inventory = Path(report["route_inventory"]["inventory_markdown"])
        route_doc_path = (root / args.write_route_doc).resolve()
        route_doc_path.parent.mkdir(parents=True, exist_ok=True)
        route_doc_path.write_text(src_inventory.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"Formal gate report: {md_path}")
    print(f"Formal gate JSON:   {json_path}")
    print(f"Overall status:     {overall}")

    if overall == STATUS_FAIL:
        return 2
    if overall == STATUS_PENDING and args.fail_on_pending:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
