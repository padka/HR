from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "architecture" / "supported_channels.md",
    REPO_ROOT / "docs" / "architecture" / "overview.md",
    REPO_ROOT / "docs" / "architecture" / "runtime-topology.md",
    REPO_ROOT / "docs" / "architecture" / "core-workflows.md",
    REPO_ROOT / "docs" / "frontend" / "route-map.md",
    REPO_ROOT / "docs" / "frontend" / "state-flows.md",
    REPO_ROOT / "docs" / "frontend" / "screen-inventory.md",
    REPO_ROOT / "docs" / "security" / "trust-boundaries.md",
    REPO_ROOT / "docs" / "qa" / "critical-flow-catalog.md",
    REPO_ROOT / "docs" / "qa" / "master-test-plan.md",
    REPO_ROOT / "docs" / "qa" / "release-gate-v2.md",
)


def _canonical_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in CANONICAL_DOCS)


def test_canonical_docs_preserve_runtime_truth_and_target_state_language() -> None:
    text = _canonical_text()

    assert "legacy candidate portal implementation" in text
    assert "future standalone candidate web flow" in text
    assert "historical MAX runtime" in text
    assert "future MAX mini-app/channel adapter" in text
    assert "bounded MAX launch/auth" in text or "bounded MAX pilot" in text
    assert "/api/max/launch" in text
    assert re.search(r"SMS\s*/\s*voice fallback", text)


def test_canonical_docs_drop_deleted_runtime_paths() -> None:
    text = _canonical_text()

    assert "candidate_portal.py" not in text
    assert "backend.apps.max_bot.app" not in text
    assert "backend.apps.max_bot.candidate_flow" not in text


def test_canonical_docs_require_openapi_repo_local_gate() -> None:
    text = _canonical_text()

    assert "make openapi-check" in text
    assert "required repo-local gate" in text


def test_canonical_docs_mark_operator_health_as_non_public() -> None:
    text = _canonical_text().lower()

    assert "/health/bot" in text
    assert "/health/notifications" in text
    assert "operator-only" in text or "authenticated operator" in text
