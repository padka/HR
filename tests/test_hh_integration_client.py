from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from backend.domain.hh_integration.client import (
    HHApiClient,
    HHApiError,
    normalize_hh_api_error,
)
from backend.domain.hh_integration.contracts import HHSyncFailureCode


@pytest.mark.asyncio
async def test_list_negotiations_collection_preserves_vacancy_id_query(monkeypatch):
    client = HHApiClient()
    request_mock = AsyncMock(return_value={"items": []})
    monkeypatch.setattr(client, "_request", request_mock)

    await client.list_negotiations_collection(
        "token-1",
        collection_url="https://api.hh.ru/negotiations/response?vacancy_id=129958197",
        manager_account_id="171136527",
        page=2,
        per_page=50,
    )

    request_mock.assert_awaited_once()
    _, path = request_mock.await_args.args[:2]
    assert "vacancy_id=129958197" in path
    assert "page=2" in path
    assert "per_page=50" in path
    assert request_mock.await_args.kwargs["manager_account_id"] == "171136527"


def test_normalize_hh_api_error_403_is_controlled_non_retryable():
    normalized = normalize_hh_api_error(
        HHApiError(
            "HH API 403 for GET /employers/emp-1/vacancies/active?client_secret=leak",
            status_code=403,
            payload={"error": "forbidden"},
        )
    )

    assert normalized.code == HHSyncFailureCode.ACCESS_FORBIDDEN
    assert normalized.retryable is False
    assert normalized.payload is None
    assert "client_secret" not in normalized.message


def test_normalize_hh_api_error_429_uses_retry_after():
    normalized = normalize_hh_api_error(
        HHApiError("HH API 429 for GET /me", status_code=429, retry_after_seconds=17)
    )

    assert normalized.code == HHSyncFailureCode.RATE_LIMITED
    assert normalized.retryable is True
    assert normalized.retry_after_seconds == 17


def test_normalize_hh_api_error_retries_only_5xx_http_errors():
    service_error = normalize_hh_api_error(
        HHApiError("HH API 502 for GET /me", status_code=502)
    )
    client_error = normalize_hh_api_error(
        HHApiError("HH API 400 for GET /me", status_code=400)
    )

    assert service_error.code == HHSyncFailureCode.PROVIDER_HTTP_ERROR
    assert service_error.retryable is True
    assert client_error.code == HHSyncFailureCode.PROVIDER_HTTP_ERROR
    assert client_error.retryable is False
