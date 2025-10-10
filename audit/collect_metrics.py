#!/usr/bin/env python3
"""Collect runtime and bundle metrics for the audit."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def run_lifespan(app):
    await app.router.startup()
    try:
        yield
    finally:
        await app.router.shutdown()


def measure_cold_start() -> float:
    from backend.apps.admin_ui.app import create_app

    app = create_app()
    start = time.perf_counter()

    async def _run() -> None:
        async with run_lifespan(app):
            pass

    asyncio.run(_run())
    return time.perf_counter() - start


def count_routes() -> int:
    from backend.apps.admin_ui.app import create_app

    app = create_app()
    return len(app.routes)


def count_models() -> int:
    import importlib

    importlib.import_module("backend.domain.models")
    Base = importlib.import_module("backend.domain.base").Base
    return len(Base.registry.mappers)


def count_tests() -> int:
    tests_dir = ROOT / "tests"
    return len(list(tests_dir.rglob("test_*.py")))


def css_bundle_metrics() -> Dict[str, Any]:
    bundle = ROOT / "backend" / "apps" / "admin_ui" / "static" / "build" / "main.css"
    info = {"exists": bundle.exists(), "size_bytes": None, "class_count": None}
    if bundle.exists():
        data = bundle.read_text(encoding="utf-8", errors="ignore")
        info["size_bytes"] = bundle.stat().st_size
        selectors = re.findall(r"\.([A-Za-z0-9\-]+)\{", data)
        info["class_count"] = len(set(selectors))
    return info


def template_tailwind_usage() -> Dict[str, Any]:
    templates_dir = ROOT / "backend" / "apps" / "admin_ui" / "templates"
    class_pattern = re.compile(r"class=\"([^\"]+)\"")
    total_classes = 0
    unique_classes: set[str] = set()
    for file in templates_dir.rglob("*.html"):
        text = file.read_text(encoding="utf-8", errors="ignore")
        for match in class_pattern.finditer(text):
            classes = match.group(1).replace("{{", " ").replace("}}", " ")
            for cls in classes.split():
                candidate = cls.strip()
                if not candidate or "{{" in candidate or "}}" in candidate:
                    continue
                unique_classes.add(candidate)
                total_classes += 1
    return {"unique_classes": len(unique_classes), "total_class_tokens": total_classes}


def read_smoke_log(path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if not path.exists():
        return result
    lines = path.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in lines:
        if line.startswith("- "):
            entries.append(line)
        if "detail:" in line:
            entries.append(line.strip())
    result["entries"] = entries
    result["raw"] = lines
    return result


def main() -> None:
    metrics: Dict[str, Any] = {}
    metrics["cold_start_seconds"] = measure_cold_start()
    metrics["route_count"] = count_routes()
    metrics["model_count"] = count_models()
    metrics["test_file_count"] = count_tests()
    metrics["css_bundle"] = css_bundle_metrics()
    metrics["template_tailwind"] = template_tailwind_usage()
    metrics["smoke_no_db"] = read_smoke_log(ROOT / "audit" / "smoke_no_db.log")
    metrics["smoke_with_db"] = read_smoke_log(ROOT / "audit" / "smoke_with_db.log")

    output = ROOT / "audit" / "METRICS.md"
    lines = ["# Runtime and Bundle Metrics", ""]
    lines.append(f"- Cold start (lifespan) time: {metrics['cold_start_seconds']:.3f}s")
    lines.append(f"- Total FastAPI routes: {metrics['route_count']}")
    lines.append(f"- SQLAlchemy model count: {metrics['model_count']}")
    lines.append(f"- Test file count: {metrics['test_file_count']}")
    css = metrics["css_bundle"]
    if css.get("exists"):
        lines.append(
            f"- main.css size: {css['size_bytes']} bytes; unique selectors: {css['class_count']}"
        )
    template_usage = metrics["template_tailwind"]
    lines.append(
        f"- Tailwind class tokens in templates: {template_usage['total_class_tokens']} (unique: {template_usage['unique_classes']})"
    )
    lines.append("")
    lines.append("## Smoke test summary")
    lines.append("")
    for mode in ("smoke_no_db", "smoke_with_db"):
        lines.append(f"### {mode}")
        entries = metrics[mode].get("entries", [])
        if not entries:
            lines.append("- no data")
        else:
            for entry in entries:
                lines.append(f"- {entry}")
        lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")

    json_output = ROOT / "audit" / "metrics.json"
    json_output.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
