from scripts.reset_postgres_proof_db import (
    _is_disposable_database_name,
    _strip_async_driver,
    validate_reset_target,
)


def test_strip_async_driver_converts_asyncpg_url():
    assert (
        _strip_async_driver("postgresql+asyncpg://user:pass@localhost:5432/rs_test")
        == "postgresql://user:pass@localhost:5432/rs_test"
    )


def test_disposable_database_name_allows_test_and_proof_suffixes():
    assert _is_disposable_database_name("rs_test")
    assert _is_disposable_database_name("rs_test_phase1")
    assert _is_disposable_database_name("rs_proof")


def test_disposable_database_name_rejects_non_test_database_names():
    assert not _is_disposable_database_name("recruitsmart")
    assert not _is_disposable_database_name("production")


def test_validate_reset_target_rejects_non_local_hosts():
    try:
        validate_reset_target("postgresql+asyncpg://user:pass@db.internal:5432/rs_test")
    except RuntimeError as exc:
        assert "non-local host" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for non-local host")


def test_validate_reset_target_rejects_non_disposable_database_names():
    try:
        validate_reset_target("postgresql+asyncpg://user:pass@localhost:5432/recruitsmart")
    except RuntimeError as exc:
        assert "non-disposable" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for non-disposable database name")


def test_validate_reset_target_accepts_local_disposable_database():
    assert (
        validate_reset_target("postgresql+asyncpg://user:pass@localhost:5432/rs_test")
        == "postgresql://user:pass@localhost:5432/rs_test"
    )
