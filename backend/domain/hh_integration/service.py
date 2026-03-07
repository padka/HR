"""Persistence services for direct HH integration."""

from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlsplit

from backend.apps.admin_ui.security import Principal
from backend.domain.hh_integration.client import HHOAuthTokens
from backend.domain.hh_integration.contracts import HHConnectionStatus
from backend.domain.hh_integration.crypto import HHSecretCipher
from backend.domain.hh_integration.models import HHConnection
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _manager_name_from_profile(payload: dict[str, Any]) -> str | None:
    first_name = str(payload.get("first_name") or "").strip()
    last_name = str(payload.get("last_name") or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part)
    return full_name or None


def _employer_info(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    employer = payload.get("employer") if isinstance(payload, dict) else None
    if not isinstance(employer, dict):
        return None, None
    employer_id = str(employer.get("id") or "").strip() or None
    employer_name = str(employer.get("name") or "").strip() or None
    return employer_id, employer_name


def _manager_info(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    manager = payload.get("manager") if isinstance(payload, dict) else None
    if isinstance(manager, dict):
        manager_id = str(manager.get("id") or "").strip() or None
        return manager_id, _manager_name_from_profile(payload)
    return (str(payload.get("id") or "").strip() or None), _manager_name_from_profile(payload)


def _manager_account_id(payload: dict[str, Any]) -> str | None:
    current = str(payload.get("current_account_id") or "").strip()
    return current or None


async def get_connection_for_principal(session: AsyncSession, principal: Principal) -> HHConnection | None:
    result = await session.execute(
        select(HHConnection).where(
            HHConnection.principal_type == principal.type,
            HHConnection.principal_id == principal.id,
        )
    )
    connection = result.scalar_one_or_none()
    if connection is not None:
        return connection

    if principal.type != "admin":
        return None

    # Historical admin integrations were stored under sentinel principal_id=-1.
    # Keep lookup backward-compatible until connections are normalized.
    fallback = await session.execute(
        select(HHConnection)
        .where(HHConnection.principal_type == "admin")
        .order_by(HHConnection.updated_at.desc(), HHConnection.id.desc())
        .limit(1)
    )
    return fallback.scalar_one_or_none()


async def get_connection_for_webhook_key(session: AsyncSession, webhook_key: str) -> HHConnection | None:
    result = await session.execute(
        select(HHConnection).where(HHConnection.webhook_url_key == webhook_key)
    )
    return result.scalar_one_or_none()


def _resolve_public_base_url(*, webhook_base_url: str | None = None, redirect_uri: str | None = None) -> str | None:
    configured = (webhook_base_url or "").strip().rstrip("/")
    if configured:
        return configured
    parsed = urlsplit((redirect_uri or "").strip())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return None


def build_connection_summary(
    connection: HHConnection | None,
    *,
    webhook_base_url: str | None = None,
    redirect_uri: str | None = None,
) -> dict[str, Any] | None:
    if connection is None:
        return None
    webhook_path = f"/api/hh-integration/webhooks/{connection.webhook_url_key}"
    webhook_url = None
    public_base_url = _resolve_public_base_url(webhook_base_url=webhook_base_url, redirect_uri=redirect_uri)
    if public_base_url:
        webhook_url = public_base_url + webhook_path
    return {
        "id": connection.id,
        "principal_type": connection.principal_type,
        "principal_id": connection.principal_id,
        "status": connection.status,
        "employer_id": connection.employer_id,
        "employer_name": connection.employer_name,
        "manager_id": connection.manager_id,
        "manager_account_id": connection.manager_account_id,
        "manager_name": connection.manager_name,
        "token_expires_at": connection.token_expires_at.isoformat() if connection.token_expires_at else None,
        "last_sync_at": connection.last_sync_at.isoformat() if connection.last_sync_at else None,
        "last_error": connection.last_error,
        "webhook_path": webhook_path,
        "webhook_url": webhook_url,
    }


def decrypt_access_token(connection: HHConnection) -> str:
    return HHSecretCipher().decrypt(connection.access_token_encrypted)


def decrypt_refresh_token(connection: HHConnection) -> str:
    return HHSecretCipher().decrypt(connection.refresh_token_encrypted)


def apply_refreshed_tokens(connection: HHConnection, tokens: HHOAuthTokens) -> HHConnection:
    cipher = HHSecretCipher()
    connection.access_token_encrypted = cipher.encrypt(tokens.access_token)
    connection.refresh_token_encrypted = cipher.encrypt(tokens.refresh_token)
    connection.token_expires_at = tokens.expires_at
    connection.status = HHConnectionStatus.ACTIVE
    connection.last_error = None
    return connection


def build_webhook_target_url(
    connection: HHConnection,
    *,
    webhook_base_url: str | None = None,
    redirect_uri: str | None = None,
) -> str:
    base = _resolve_public_base_url(webhook_base_url=webhook_base_url, redirect_uri=redirect_uri)
    if not base:
        raise ValueError("HH_WEBHOOK_BASE_URL or HH_REDIRECT_URI is not configured")
    return f"{base}/api/hh-integration/webhooks/{connection.webhook_url_key}"


async def upsert_hh_connection(
    session: AsyncSession,
    *,
    principal: Principal,
    tokens: HHOAuthTokens,
    me_payload: dict[str, Any],
    manager_accounts_payload: dict[str, Any],
) -> HHConnection:
    cipher = HHSecretCipher()
    connection = await get_connection_for_principal(session, principal)
    if connection is None:
        connection = HHConnection(
            principal_type=principal.type,
            principal_id=principal.id,
            webhook_url_key=secrets.token_urlsafe(24).rstrip("="),
            access_token_encrypted="",
            refresh_token_encrypted="",
            profile_payload={},
        )
        session.add(connection)

    employer_id, employer_name = _employer_info(me_payload)
    manager_id, manager_name = _manager_info(me_payload)

    connection.employer_id = employer_id
    connection.employer_name = employer_name
    connection.manager_id = manager_id
    connection.manager_account_id = _manager_account_id(manager_accounts_payload)
    connection.manager_name = manager_name
    connection.status = HHConnectionStatus.ACTIVE
    connection.access_token_encrypted = cipher.encrypt(tokens.access_token)
    connection.refresh_token_encrypted = cipher.encrypt(tokens.refresh_token)
    connection.token_expires_at = tokens.expires_at
    connection.last_error = None
    connection.profile_payload = {
        "me": me_payload,
        "manager_accounts": manager_accounts_payload,
    }

    await session.flush()
    return connection
