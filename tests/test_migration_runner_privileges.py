from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.migrations.runner import _assert_schema_create_privilege


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeConnection:
    def __init__(self, *, dialect_name: str, can_create: bool = True, user: str = "app_user"):
        self.dialect = SimpleNamespace(name=dialect_name)
        self._can_create = can_create
        self._user = user

    def execute(self, statement, params=None):  # noqa: ANN001
        sql = str(statement)
        if "has_schema_privilege" in sql:
            return _ScalarResult(self._can_create)
        if "current_user" in sql:
            return _ScalarResult(self._user)
        return _ScalarResult(None)


def test_preflight_skips_non_postgres() -> None:
    conn = _FakeConnection(dialect_name="sqlite")
    _assert_schema_create_privilege(conn)


def test_preflight_passes_when_create_privilege_present() -> None:
    conn = _FakeConnection(dialect_name="postgresql", can_create=True, user="migrator")
    _assert_schema_create_privilege(conn)


def test_preflight_fails_without_create_privilege() -> None:
    conn = _FakeConnection(dialect_name="postgresql", can_create=False, user="app_user")
    with pytest.raises(RuntimeError, match="MIGRATIONS_DATABASE_URL"):
        _assert_schema_create_privilege(conn)
