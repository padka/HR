from __future__ import annotations

import logging

import pytest
from sqlalchemy import select

from backend.apps.admin_ui.services.recruiters import create_recruiter
from backend.core.db import async_session
from backend.core.passwords import verify_password
from backend.domain.auth_account import AuthAccount


@pytest.mark.asyncio
async def test_create_recruiter_generates_random_password_when_env_missing(monkeypatch, caplog):
    monkeypatch.delenv("RECRUITER_DEFAULT_PASSWORD", raising=False)

    with caplog.at_level(logging.WARNING, logger="backend.apps.admin_ui.services.recruiters"):
        result = await create_recruiter({"name": "Secure Recruiter", "tz": "Europe/Moscow", "active": True})

    assert result["ok"] is True
    assert result["auth_account_created"] is True
    assert result["login"] == str(result["recruiter_id"])
    assert isinstance(result["temp_password"], str)
    assert len(result["temp_password"]) == 16
    assert "RECRUITER_DEFAULT_PASSWORD not set" in caplog.text
    assert result["temp_password"] not in caplog.text

    async with async_session() as session:
        account = await session.scalar(
            select(AuthAccount).where(
                AuthAccount.principal_type == "recruiter",
                AuthAccount.principal_id == result["recruiter_id"],
            )
        )

    assert account is not None
    assert verify_password(result["temp_password"], account.password_hash)


@pytest.mark.asyncio
async def test_create_recruiter_uses_env_password_when_configured(monkeypatch, caplog):
    monkeypatch.setenv("RECRUITER_DEFAULT_PASSWORD", "Configured!234")

    with caplog.at_level(logging.WARNING, logger="backend.apps.admin_ui.services.recruiters"):
        result = await create_recruiter({"name": "Configured Recruiter", "tz": "Europe/Moscow", "active": True})

    assert result["ok"] is True
    assert result["auth_account_created"] is True
    assert result["temp_password"] == "Configured!234"
    assert "RECRUITER_DEFAULT_PASSWORD not set" not in caplog.text

    async with async_session() as session:
        account = await session.scalar(
            select(AuthAccount).where(
                AuthAccount.principal_type == "recruiter",
                AuthAccount.principal_id == result["recruiter_id"],
            )
        )

    assert account is not None
    assert verify_password("Configured!234", account.password_hash)
