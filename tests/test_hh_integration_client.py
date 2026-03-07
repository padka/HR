from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from backend.domain.hh_integration.client import HHApiClient


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
