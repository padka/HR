"""Render demo templates to static HTML previews."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_demo import DEMO_ROUTES, templates

OUTPUT_DIR = Path("previews")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class DummyRequest:
    """Minimal request stub for offline Jinja rendering."""

    def __init__(self, path: str) -> None:
        self.url = SimpleNamespace(path=path, hostname="demo.local")
        self.query_params: dict[str, str] = {}


def render_all() -> None:
    for route in DEMO_ROUTES:
        context = route.context_factory()
        context["request"] = DummyRequest(route.path)
        template = templates.get_template(route.template)
        html = template.render(context)
        slug = route.slug or route.path.strip("/") or "index"
        output_path = OUTPUT_DIR / f"{slug}.html"
        output_path.write_text(html, encoding="utf-8")
        print(f"Rendered {route.path} → {output_path}")


if __name__ == "__main__":
    render_all()
