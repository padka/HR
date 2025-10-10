"""Compute CSS bundle sizes and update the audit report."""

from __future__ import annotations

import gzip
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CSS_BUNDLE = Path("backend/apps/admin_ui/static/build/main.css")
REPORT_FILE = Path("audit/CSS_SIZE.md")

RAW_BUDGET_BYTES = 90 * 1024  # 90 KB raw
GZIP_BUDGET_BYTES = 70 * 1024  # 70 KB gzip


@dataclass
class SizeResult:
    label: str
    bytes: int
    budget: int

    @property
    def status(self) -> str:
        return "WARN" if self.bytes > self.budget else "OK"

    @property
    def human_size(self) -> str:
        return f"{self.bytes / 1024:.1f} KB"

    @property
    def human_budget(self) -> str:
        return f"{self.budget / 1024:.1f} KB"


def _gzip_size(data: bytes) -> int:
    return len(gzip.compress(data))


def _ensure_bundle_exists() -> bytes:
    if not CSS_BUNDLE.exists():
        raise SystemExit(f"CSS bundle not found at {CSS_BUNDLE}")
    return CSS_BUNDLE.read_bytes()


def _build_table(rows: Iterable[SizeResult]) -> str:
    header = "| Metric | Size | Budget | Status |"
    divider = "| --- | --- | --- | --- |"
    body_lines = [
        f"| {row.label} | {row.human_size} | {row.human_budget} | {row.status} |"
        for row in rows
    ]
    return "\n".join([header, divider, *body_lines])


def main() -> None:
    bundle_bytes = _ensure_bundle_exists()
    raw_size = len(bundle_bytes)
    gzip_size = _gzip_size(bundle_bytes)

    results = [
        SizeResult("Raw", raw_size, RAW_BUDGET_BYTES),
        SizeResult("Gzip", gzip_size, GZIP_BUDGET_BYTES),
    ]

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    report_lines = [
        "# CSS Bundle Size",
        "",
        _build_table(results),
        "",
        "> Budgets: Raw ≤ 90 KB, Gzip ≤ 70 KB.",
    ]
    REPORT_FILE.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    for result in results:
        prefix = "WARN" if result.status == "WARN" else "OK"
        print(
            f"[{prefix}] {result.label} bundle size: {result.human_size} "
            f"(budget {result.human_budget})"
        )

    if any(result.status == "WARN" for result in results):
        print("WARN: CSS bundle exceeds the current budget.")


if __name__ == "__main__":
    main()
