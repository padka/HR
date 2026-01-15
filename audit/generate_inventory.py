#!/usr/bin/env python3
"""Generate inventory information for the HR admin project."""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {"venv", "node_modules", "__pycache__", "dist", "build", ".git", ".mypy_cache", ".pytest_cache"}


def iter_tree(root: Path) -> List[str]:
    lines: List[str] = []
    prefix_stack: List[str] = []

    def walk(dir_path: Path, prefix: str = "") -> None:
        entries = [p for p in dir_path.iterdir() if p.name not in EXCLUDE_DIRS]
        entries.sort(key=lambda p: (p.is_file(), p.name))
        for index, entry in enumerate(entries):
            connector = "└── " if index == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                extension = "    " if index == len(entries) - 1 else "│   "
                walk(entry, prefix + extension)

    walk(root)
    return lines


def read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def load_toml(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        if sys.version_info >= (3, 11):
            import tomllib
        else:  # pragma: no cover - Python <3.11 fallback
            import tomli as tomllib  # type: ignore
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": str(exc)}


def load_json(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": str(exc)}


def gather_python_dependencies(pyproject_data: Dict[str, Any] | None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "project": {},
        "optional": {},
    }
    if not pyproject_data:
        return result
    project = pyproject_data.get("project", {})
    if project:
        result["project"] = {
            "name": project.get("name"),
            "version": project.get("version"),
            "dependencies": project.get("dependencies", []),
        }
        result["optional"] = project.get("optional-dependencies", {})
    tool = pyproject_data.get("tool", {})
    if "poetry" in tool:
        poetry = tool["poetry"]
        result["poetry"] = {
            "dependencies": poetry.get("dependencies", {}),
            "dev-dependencies": poetry.get("dev-dependencies", {}),
        }
    return result


def gather_npm_dependencies(package_json: Dict[str, Any] | None) -> Dict[str, Any]:
    if not package_json:
        return {}
    return {
        "name": package_json.get("name"),
        "version": package_json.get("version"),
        "scripts": package_json.get("scripts", {}),
        "dependencies": package_json.get("dependencies", {}),
        "devDependencies": package_json.get("devDependencies", {}),
    }


def format_routes(route) -> Dict[str, Any]:
    methods = sorted(m for m in getattr(route, "methods", []) if m not in {"HEAD", "OPTIONS"})
    return {
        "path": getattr(route, "path", None),
        "name": getattr(route.endpoint, "__name__", None) if hasattr(route, "endpoint") else None,
        "methods": methods,
        "endpoint": getattr(route.endpoint, "__qualname__", None) if hasattr(route, "endpoint") else None,
        "app_name": getattr(route.app, "title", None) if hasattr(route, "app") else None,
    }


def gather_fastapi_app(module_path: str, attr: str = "app") -> Dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    try:
        module = importlib.import_module(module_path)
        app = getattr(module, attr)
    except Exception as exc:
        return {"error": f"Failed to import {module_path}:{attr}: {exc}"}

    routes = [format_routes(route) for route in getattr(app, "routes", [])]
    middleware = [
        {
            "cls": getattr(mw.cls, "__name__", str(mw.cls)),
            "options": getattr(mw, "kwargs", {}),
        }
        for mw in getattr(app, "user_middleware", [])
    ]
    dependencies = list(getattr(app.router, "dependencies", []))
    depends = []
    for dep in dependencies:
        target = dep.dependency
        depends.append(getattr(target, "__qualname__", repr(target)))

    return {
        "module": module_path,
        "routes": routes,
        "middleware": middleware,
        "dependencies": depends,
    }


def gather_sqlalchemy_models() -> Dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    try:
        importlib.import_module("backend.domain.models")
        base_module = importlib.import_module("backend.domain.base")
        Base = getattr(base_module, "Base")
    except Exception as exc:
        return {"error": f"Failed to import models: {exc}"}

    models: List[Dict[str, Any]] = []
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        table = mapper.local_table
        models.append(
            {
                "model": f"{cls.__module__}.{cls.__name__}",
                "table": table.name,
                "columns": [col.name for col in table.columns],
            }
        )
    models.sort(key=lambda item: item["model"])
    return {"models": models, "count": len(models)}


def gather_migrations() -> Dict[str, Any]:
    versions_dir = ROOT / "backend" / "migrations" / "versions"
    if not versions_dir.exists():
        return {"versions": []}
    versions = []
    for path in sorted(versions_dir.glob("*.py")):
        versions.append({"file": path.name, "size": path.stat().st_size})
    return {"versions": versions, "count": len(versions)}


def count_tests() -> Dict[str, Any]:
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        return {"error": "tests directory missing"}
    test_files = sorted([p for p in tests_dir.rglob("test_*.py")])
    total_functions = 0
    pattern = re.compile(r"^def test_", re.MULTILINE)
    for file in test_files:
        try:
            text = file.read_text(encoding="utf-8")
        except Exception:
            continue
        total_functions += len(pattern.findall(text))
    return {
        "test_files": [str(p.relative_to(ROOT)) for p in test_files],
        "file_count": len(test_files),
        "test_functions": total_functions,
    }


def list_ci_configs() -> List[str]:
    workflows_dir = ROOT / ".github" / "workflows"
    if not workflows_dir.exists():
        return []
    return [str(p.relative_to(ROOT)) for p in sorted(workflows_dir.glob("*.yml"))]


def find_secret_candidates() -> List[str]:
    candidates: List[str] = []
    patterns = re.compile(r"(API_KEY|TOKEN|SECRET|PASSWORD|CLIENT_ID|CLIENT_SECRET)", re.IGNORECASE)
    for path in ROOT.rglob("*"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.is_dir():
            continue
        if path.suffix in {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if patterns.search(text):
            rel = path.relative_to(ROOT)
            candidates.append(str(rel))
    return sorted(candidates)


def list_static_assets() -> Dict[str, Any]:
    static_dirs = []
    for candidate in [ROOT / "backend" / "apps" / "admin_ui" / "static", ROOT / "admin_server" / "static"]:
        if candidate.exists():
            assets = []
            for path in sorted(candidate.rglob("*")):
                if path.is_file():
                    assets.append(str(path.relative_to(ROOT)))
            static_dirs.append({"path": str(candidate.relative_to(ROOT)), "assets": assets})
    favicons = []
    for pattern in ["favicon", "apple-touch"]:
        for path in ROOT.rglob(f"*{pattern}*"):
            if path.suffix in {".ico", ".png", ".svg"}:
                favicons.append(str(path.relative_to(ROOT)))
    css_build = []
    for path in ROOT.rglob("main.css"):
        if "static" in path.parts:
            css_build.append(str(path.relative_to(ROOT)))
    return {"static_dirs": static_dirs, "favicons": sorted(set(favicons)), "css_build_files": sorted(css_build)}


def main() -> None:
    tree_lines = iter_tree(ROOT)
    pyproject_path = ROOT / "pyproject.toml"
    package_json_path = ROOT / "package.json"
    package_lock_path = ROOT / "package-lock.json"
    tailwind_config = ROOT / "tailwind.config.js"
    postcss_config = ROOT / "postcss.config.cjs"

    pyproject_data = load_toml(pyproject_path)
    package_json_data = load_json(package_json_path)

    inventory: Dict[str, Any] = {
        "tree": tree_lines,
        "configs": {
            "pyproject.toml": str(pyproject_path.relative_to(ROOT)) if pyproject_path.exists() else None,
            "package.json": str(package_json_path.relative_to(ROOT)) if package_json_path.exists() else None,
            "package-lock.json": str(package_lock_path.relative_to(ROOT)) if package_lock_path.exists() else None,
            "tailwind.config": str(tailwind_config.relative_to(ROOT)) if tailwind_config.exists() else None,
            "postcss.config": str(postcss_config.relative_to(ROOT)) if postcss_config.exists() else None,
        },
        "python": gather_python_dependencies(pyproject_data),
        "npm": gather_npm_dependencies(package_json_data),
        "fastapi": {
            "admin_ui": gather_fastapi_app("backend.apps.admin_ui.app", "app"),
            "admin_api": gather_fastapi_app("backend.apps.admin_api.main", "app"),
        },
        "sqlalchemy": gather_sqlalchemy_models(),
        "migrations": gather_migrations(),
        "tests": count_tests(),
        "ci": list_ci_configs(),
        "secrets": find_secret_candidates(),
        "static": list_static_assets(),
    }

    audit_dir = ROOT / "audit"
    audit_dir.mkdir(exist_ok=True)

    inventory_json_path = audit_dir / "INVENTORY.json"
    inventory_json_path.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")

    # Build markdown summary
    md_lines = ["# Project Inventory", ""]
    md_lines.append("## Repository Tree (trimmed)")
    md_lines.append("```")
    md_lines.extend(tree_lines[:4000])
    md_lines.append("```")
    md_lines.append("")

    md_lines.append("## Configuration Files")
    md_lines.append("")
    for key, value in inventory["configs"].items():
        status = value if value else "missing"
        md_lines.append(f"- **{key}**: {status}")
    md_lines.append("")

    md_lines.append("## Python Project Metadata")
    md_lines.append("")
    python_meta = inventory["python"]
    project_meta = python_meta.get("project", {})
    md_lines.append(f"- Name: `{project_meta.get('name')}`")
    md_lines.append(f"- Version: `{project_meta.get('version')}`")
    dependencies = project_meta.get("dependencies", [])
    if dependencies:
        md_lines.append("- Dependencies:")
        for dep in dependencies:
            md_lines.append(f"  - `{dep}`")
    optional = python_meta.get("optional", {})
    if optional:
        md_lines.append("- Optional Dependencies:")
        for group, deps in optional.items():
            md_lines.append(f"  - **{group}**:")
            for dep in deps:
                md_lines.append(f"    - `{dep}`")
    poetry_meta = python_meta.get("poetry")
    if poetry_meta:
        md_lines.append("- Poetry:")
        for key, values in poetry_meta.items():
            md_lines.append(f"  - {key}:")
            if isinstance(values, dict):
                for dep, constraint in values.items():
                    md_lines.append(f"    - `{dep}`: `{constraint}`")
    md_lines.append("")

    md_lines.append("## Node Package Metadata")
    md_lines.append("")
    npm_meta = inventory["npm"]
    if npm_meta:
        md_lines.append(f"- Name: `{npm_meta.get('name')}`")
        md_lines.append(f"- Version: `{npm_meta.get('version')}`")
        scripts = npm_meta.get("scripts", {})
        if scripts:
            md_lines.append("- Scripts:")
            for name, cmd in scripts.items():
                md_lines.append(f"  - `{name}`: `{cmd}`")
        deps = npm_meta.get("dependencies", {})
        if deps:
            md_lines.append("- Dependencies:")
            for name, version in deps.items():
                md_lines.append(f"  - `{name}`: `{version}`")
        dev_deps = npm_meta.get("devDependencies", {})
        if dev_deps:
            md_lines.append("- Dev Dependencies:")
            for name, version in dev_deps.items():
                md_lines.append(f"  - `{name}`: `{version}`")
    else:
        md_lines.append("- package.json missing or unreadable")
    md_lines.append("")

    md_lines.append("## FastAPI Applications")
    md_lines.append("")
    for key, data in inventory["fastapi"].items():
        md_lines.append(f"### {key}")
        if "error" in data:
            md_lines.append(f"- Error: {data['error']}")
            md_lines.append("")
            continue
        md_lines.append(f"- Routes: {len(data['routes'])}")
        md_lines.append("- Middleware:")
        if data["middleware"]:
            for mw in data["middleware"]:
                md_lines.append(f"  - `{mw['cls']}` {mw['options']}")
        else:
            md_lines.append("  - *(none)*")
        md_lines.append("- Dependencies:")
        if data["dependencies"]:
            for dep in data["dependencies"]:
                md_lines.append(f"  - `{dep}`")
        else:
            md_lines.append("  - *(none)*")
        md_lines.append("- Route table:")
        for route in data["routes"]:
            md_lines.append(
                f"  - `{route['path']}` → `{route['endpoint']}` methods={route['methods']}"
            )
        md_lines.append("")

    md_lines.append("## SQLAlchemy Models")
    md_lines.append("")
    sqlalchemy_info = inventory["sqlalchemy"]
    if "error" in sqlalchemy_info:
        md_lines.append(f"- Error: {sqlalchemy_info['error']}")
    else:
        md_lines.append(f"- Total models: {sqlalchemy_info['count']}")
        for model in sqlalchemy_info["models"]:
            cols = ", ".join(model["columns"])
            md_lines.append(f"  - `{model['model']}` → `{model['table']}` ({cols})")
    md_lines.append("")

    md_lines.append("## Migrations")
    md_lines.append("")
    migrations = inventory["migrations"]
    md_lines.append(f"- Version files: {migrations.get('count', 0)}")
    for version in migrations.get("versions", []):
        md_lines.append(f"  - `{version['file']}` ({version['size']} bytes)")
    md_lines.append("")

    md_lines.append("## Tests")
    md_lines.append("")
    tests_info = inventory["tests"]
    if "error" in tests_info:
        md_lines.append(f"- Error: {tests_info['error']}")
    else:
        md_lines.append(f"- Test files: {tests_info['file_count']}")
        md_lines.append(f"- Test functions: {tests_info['test_functions']}")
        for file in tests_info["test_files"]:
            md_lines.append(f"  - `{file}`")
    md_lines.append("")

    md_lines.append("## CI Workflows")
    md_lines.append("")
    ci_files = inventory["ci"]
    if ci_files:
        for file in ci_files:
            md_lines.append(f"- `{file}`")
    else:
        md_lines.append("- *(none)*")
    md_lines.append("")

    md_lines.append("## Potential Secret Matches")
    md_lines.append("")
    secret_files = inventory["secrets"]
    if secret_files:
        for file in secret_files:
            md_lines.append(f"- `{file}`")
    else:
        md_lines.append("- *(none found)*")
    md_lines.append("")

    md_lines.append("## Static Assets")
    md_lines.append("")
    static_info = inventory["static"]
    for entry in static_info.get("static_dirs", []):
        md_lines.append(f"- `{entry['path']}`")
        for asset in entry["assets"][:40]:
            md_lines.append(f"  - `{asset}`")
        if len(entry["assets"]) > 40:
            md_lines.append(f"  - ... ({len(entry['assets']) - 40} more)")
    if static_info.get("favicons"):
        md_lines.append("- Favicons:")
        for icon in static_info["favicons"]:
            md_lines.append(f"  - `{icon}`")
    if static_info.get("css_build_files"):
        md_lines.append("- CSS builds:")
        for css in static_info["css_build_files"]:
            md_lines.append(f"  - `{css}`")
    md_lines.append("")

    inventory_md_path = audit_dir / "INVENTORY.md"
    inventory_md_path.write_text("\n".join(md_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
