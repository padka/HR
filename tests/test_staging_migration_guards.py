"""Regression coverage for code-only staging migration guards."""

from types import SimpleNamespace


def test_admin_ui_auto_migrate_skips_staging(monkeypatch):
    from backend.apps.admin_ui import app as app_module

    called = False

    def fake_upgrade_to_head() -> None:
        nonlocal called
        called = True

    monkeypatch.setenv("AUTO_MIGRATE", "true")
    monkeypatch.setenv("RUN_MIGRATIONS", "true")
    monkeypatch.setattr(app_module, "upgrade_to_head", fake_upgrade_to_head)

    assert app_module._auto_upgrade_schema_if_needed(SimpleNamespace(environment="staging")) is False
    assert called is False


def test_admin_ui_auto_migrate_respects_run_migrations_false(monkeypatch):
    from backend.apps.admin_ui import app as app_module

    called = False

    def fake_upgrade_to_head() -> None:
        nonlocal called
        called = True

    monkeypatch.setenv("AUTO_MIGRATE", "true")
    monkeypatch.setenv("RUN_MIGRATIONS", "false")
    monkeypatch.setattr(app_module, "upgrade_to_head", fake_upgrade_to_head)

    assert app_module._auto_upgrade_schema_if_needed(SimpleNamespace(environment="development")) is False
    assert called is False


def test_admin_ui_auto_migrate_still_runs_for_development_default(monkeypatch):
    from backend.apps.admin_ui import app as app_module

    called = False

    def fake_upgrade_to_head() -> None:
        nonlocal called
        called = True

    monkeypatch.delenv("AUTO_MIGRATE", raising=False)
    monkeypatch.delenv("RUN_MIGRATIONS", raising=False)
    monkeypatch.setattr(app_module, "upgrade_to_head", fake_upgrade_to_head)

    assert app_module._auto_upgrade_schema_if_needed(SimpleNamespace(environment="development")) is True
    assert called is True


def test_deploy_scripts_require_explicit_code_only_approval():
    deploy_script = open("scripts/deploy_production.sh", encoding="utf-8").read()
    smoke_script = open("scripts/prod_smoke.sh", encoding="utf-8").read()

    assert "RUN_MIGRATIONS=false requires CODE_ONLY_DEPLOY_APPROVED=true" in deploy_script
    assert "has_run_migrations" in deploy_script
    assert "MIGRATION_HISTORY_RECONCILED" in deploy_script
    assert "docker compose up -d --no-deps admin_ui admin_api bot" in deploy_script
    assert "RUN_MIGRATIONS=false requires CODE_ONLY_DEPLOY_APPROVED=true" in smoke_script
    assert "Migration history is not reconciled; refusing to run migrations" in smoke_script
