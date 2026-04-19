from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import check_openapi_drift
from scripts.export_openapi import OpenAPITarget


def _write_schema(path: Path, *, paths: dict) -> None:
    path.write_text(
        json.dumps({"openapi": "3.1.0", "info": {"title": "test", "version": "1"}, "paths": paths}),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _reset_openapi_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("RECRUITSMART_OPENAPI_MODE", raising=False)
    yield
    monkeypatch.delenv("RECRUITSMART_OPENAPI_MODE", raising=False)


def test_openapi_drift_check_fails_closed_on_live_import_error(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    target_path = tmp_path / "tracked.json"
    _write_schema(target_path, paths={})
    monkeypatch.setattr(
        check_openapi_drift,
        "TARGETS",
        (OpenAPITarget(name="admin_ui", path=target_path, importer="x:y"),),
    )

    def _boom(_target_name: str) -> dict:
        raise RuntimeError("import exploded")

    monkeypatch.setattr(check_openapi_drift, "build_live_schema", _boom)

    assert check_openapi_drift.main() == 1
    output = capsys.readouterr().out
    assert "failed closed" in output.lower()
    assert "import exploded" in output


def test_openapi_drift_check_returns_non_zero_on_schema_drift(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    target_path = tmp_path / "tracked.json"
    _write_schema(target_path, paths={})
    monkeypatch.setattr(
        check_openapi_drift,
        "TARGETS",
        (OpenAPITarget(name="admin_ui", path=target_path, importer="x:y"),),
    )
    monkeypatch.setattr(
        check_openapi_drift,
        "build_live_schema",
        lambda _target_name: {
            "openapi": "3.1.0",
            "info": {"title": "live", "version": "1"},
            "paths": {"/live": {"get": {"responses": {"200": {"description": "ok"}}}}},
        },
    )

    assert check_openapi_drift.main() == 1
    output = capsys.readouterr().out
    assert "openapi drift detected" in output.lower()


def test_openapi_drift_check_returns_zero_when_schema_matches(
    monkeypatch,
    tmp_path: Path,
) -> None:
    schema = {
        "openapi": "3.1.0",
        "info": {"title": "live", "version": "1"},
        "paths": {"/live": {"get": {"responses": {"200": {"description": "ok"}}}}},
    }
    target_path = tmp_path / "tracked.json"
    target_path.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr(
        check_openapi_drift,
        "TARGETS",
        (OpenAPITarget(name="admin_ui", path=target_path, importer="x:y"),),
    )
    monkeypatch.setattr(check_openapi_drift, "build_live_schema", lambda _target_name: schema)

    assert check_openapi_drift.main() == 0
