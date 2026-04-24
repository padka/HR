"""Thin HH API client wrapper for direct integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from backend.core.settings import get_settings
from backend.domain.hh_integration.contracts import (
    DEFAULT_HH_WEBHOOK_ACTIONS,
    HHSyncFailureCode,
)


class HHApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,
        retry_after_seconds: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class HHNormalizedError:
    code: str
    message: str
    retryable: bool
    status_code: int | None = None
    payload: Any = None
    retry_after_seconds: int | None = None


@dataclass(frozen=True)
class HHOAuthTokens:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

    @property
    def expires_at(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=max(int(self.expires_in or 0), 0))


class HHApiClient:
    def __init__(self, *, http_client: httpx.AsyncClient | None = None):
        settings = get_settings()
        self._base_url = settings.hh_api_base_url.rstrip("/")
        self._authorize_url = settings.hh_oauth_authorize_url.rstrip("/")
        self._client_id = settings.hh_client_id
        self._client_secret = settings.hh_client_secret
        self._redirect_uri = settings.hh_redirect_uri
        self._user_agent = settings.hh_user_agent
        self._http_client = http_client

    def _headers(self, *, access_token: str | None = None, manager_account_id: str | None = None) -> dict[str, str]:
        headers = {
            "HH-User-Agent": self._user_agent,
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        if manager_account_id:
            headers["X-Manager-Account-Id"] = manager_account_id
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        access_token: str | None = None,
        manager_account_id: str | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = path if path.startswith("http") else f"{self._base_url}{path}"
        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(timeout=20)
        try:
            response = await client.request(
                method,
                url,
                headers=self._headers(access_token=access_token, manager_account_id=manager_account_id),
                params=params,
                data=data,
                json=json_body,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            payload: Any = None
            try:
                payload = exc.response.json()
            except Exception:
                payload = exc.response.text[:500]
            retry_after_seconds = _parse_retry_after(exc.response.headers.get("retry-after"))
            raise HHApiError(
                f"HH API {exc.response.status_code} for {method} {urlsplit(url).path}",
                status_code=exc.response.status_code,
                payload=payload,
                retry_after_seconds=retry_after_seconds,
            ) from exc
        except httpx.RequestError as exc:
            raise HHApiError(f"HH API transport error for {method} {url}: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()

        content_type = (response.headers.get("content-type") or "").lower()
        if "json" in content_type:
            return response.json()
        if response.text:
            return response.text
        return None

    async def exchange_authorization_code(self, code: str) -> HHOAuthTokens:
        payload = await self._request(
            "POST",
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "redirect_uri": self._redirect_uri,
            },
        )
        return HHOAuthTokens(
            access_token=str(payload.get("access_token") or ""),
            refresh_token=str(payload.get("refresh_token") or ""),
            token_type=str(payload.get("token_type") or "Bearer"),
            expires_in=int(payload.get("expires_in") or 0),
        )

    async def refresh_access_token(self, refresh_token: str) -> HHOAuthTokens:
        payload = await self._request(
            "POST",
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": refresh_token,
            },
        )
        return HHOAuthTokens(
            access_token=str(payload.get("access_token") or ""),
            refresh_token=str(payload.get("refresh_token") or ""),
            token_type=str(payload.get("token_type") or "Bearer"),
            expires_in=int(payload.get("expires_in") or 0),
        )

    async def get_me(self, access_token: str) -> dict[str, Any]:
        payload = await self._request("GET", "/me", access_token=access_token)
        return payload if isinstance(payload, dict) else {}

    async def get_manager_accounts(self, access_token: str) -> dict[str, Any]:
        payload = await self._request("GET", "/manager_accounts/mine", access_token=access_token)
        return payload if isinstance(payload, dict) else {}

    async def list_vacancies(
        self,
        access_token: str,
        *,
        employer_id: str,
        manager_account_id: str | None = None,
        page: int = 0,
        per_page: int = 50,
    ) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            f"/employers/{employer_id}/vacancies/active",
            access_token=access_token,
            manager_account_id=manager_account_id,
            params={"page": page, "per_page": per_page},
        )
        return payload if isinstance(payload, dict) else {}

    async def list_negotiation_collections(
        self,
        access_token: str,
        *,
        manager_account_id: str | None = None,
        vacancy_id: str | None = None,
        with_generated_collections: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if vacancy_id:
            params["vacancy_id"] = vacancy_id
        if with_generated_collections:
            params["with_generated_collections"] = "true"
        payload = await self._request(
            "GET",
            "/negotiations",
            access_token=access_token,
            manager_account_id=manager_account_id,
            params=params or None,
        )
        return payload if isinstance(payload, dict) else {}

    async def list_negotiations_collection(
        self,
        access_token: str,
        *,
        collection_url: str,
        manager_account_id: str | None = None,
        page: int = 0,
        per_page: int = 20,
    ) -> dict[str, Any]:
        url_parts = urlsplit(collection_url)
        merged_query = dict(parse_qsl(url_parts.query, keep_blank_values=True))
        merged_query.update({"page": str(page), "per_page": str(per_page)})
        request_url = urlunsplit(
            (
                url_parts.scheme,
                url_parts.netloc,
                url_parts.path,
                urlencode(merged_query),
                url_parts.fragment,
            )
        )
        payload = await self._request(
            "GET",
            request_url,
            access_token=access_token,
            manager_account_id=manager_account_id,
        )
        return payload if isinstance(payload, dict) else {}

    async def get_resume(
        self,
        access_token: str,
        *,
        resume_id: str | None = None,
        resume_url: str | None = None,
        manager_account_id: str | None = None,
    ) -> dict[str, Any]:
        if not resume_url and not resume_id:
            raise ValueError("resume_id or resume_url is required")
        payload = await self._request(
            "GET",
            resume_url or f"/resumes/{resume_id}",
            access_token=access_token,
            manager_account_id=manager_account_id,
        )
        return payload if isinstance(payload, dict) else {}

    async def list_webhook_subscriptions(
        self,
        access_token: str,
        *,
        manager_account_id: str | None = None,
    ) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            "/webhook/subscriptions",
            access_token=access_token,
            manager_account_id=manager_account_id,
        )
        return payload if isinstance(payload, dict) else {}

    async def create_webhook_subscription(
        self,
        access_token: str,
        *,
        url: str,
        manager_account_id: str | None = None,
        action_types: tuple[str, ...] = DEFAULT_HH_WEBHOOK_ACTIONS,
    ) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            "/webhook/subscriptions",
            access_token=access_token,
            manager_account_id=manager_account_id,
            json_body={
                "url": url,
                "actions": [{"type": item} for item in action_types],
            },
        )
        return payload if isinstance(payload, dict) else {}

    async def execute_negotiation_action(
        self,
        access_token: str,
        *,
        action_url: str,
        method: str,
        manager_account_id: str | None = None,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request(
            method.upper(),
            action_url,
            access_token=access_token,
            manager_account_id=manager_account_id,
            json_body=arguments or None,
        )


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def normalize_hh_api_error(error: HHApiError) -> HHNormalizedError:
    if error.status_code == 401:
        return HHNormalizedError(
            code=HHSyncFailureCode.TOKEN_REFRESH_REQUIRED,
            message=str(error),
            retryable=True,
            status_code=error.status_code,
            payload=error.payload,
            retry_after_seconds=error.retry_after_seconds,
        )
    if error.status_code == 403:
        return HHNormalizedError(
            code=HHSyncFailureCode.ACCESS_FORBIDDEN,
            message="HH access forbidden for this employer or manager account",
            retryable=False,
            status_code=error.status_code,
            payload=None,
            retry_after_seconds=None,
        )
    if error.status_code == 404:
        return HHNormalizedError(
            code=HHSyncFailureCode.NOT_FOUND,
            message=str(error),
            retryable=False,
            status_code=error.status_code,
            payload=None,
            retry_after_seconds=None,
        )
    if error.status_code == 429:
        return HHNormalizedError(
            code=HHSyncFailureCode.RATE_LIMITED,
            message=str(error),
            retryable=True,
            status_code=error.status_code,
            payload=None,
            retry_after_seconds=error.retry_after_seconds,
        )
    if error.status_code is not None:
        return HHNormalizedError(
            code=HHSyncFailureCode.PROVIDER_HTTP_ERROR,
            message=str(error),
            retryable=500 <= int(error.status_code) < 600,
            status_code=error.status_code,
            payload=None,
            retry_after_seconds=error.retry_after_seconds,
        )
    return HHNormalizedError(
        code=HHSyncFailureCode.TRANSPORT_ERROR,
        message=str(error),
        retryable=True,
        status_code=error.status_code,
        payload=None,
        retry_after_seconds=error.retry_after_seconds,
    )
