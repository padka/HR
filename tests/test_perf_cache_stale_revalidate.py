from __future__ import annotations

import asyncio

import pytest

from backend.apps.admin_ui.perf.cache.readthrough import get_or_compute
from backend.core import microcache


@pytest.mark.asyncio
async def test_get_or_compute_serves_stale_and_refreshes_in_background(monkeypatch):
    # Enable microcache during this test (it's disabled by default under pytest).
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    microcache.clear()

    calls = 0
    refreshed = asyncio.Event()

    async def compute() -> dict:
        nonlocal calls
        calls += 1
        if calls >= 2:
            refreshed.set()
        return {"v": calls}

    key = "perf:test:stale:v1"

    v1 = await get_or_compute(
        key,
        expected_type=dict,
        ttl_seconds=0.01,
        stale_seconds=1.0,
        compute=compute,
    )
    assert v1 == {"v": 1}

    # Let the fresh TTL expire, but remain within stale window.
    await asyncio.sleep(0.02)

    v_stale = await get_or_compute(
        key,
        expected_type=dict,
        ttl_seconds=0.01,
        stale_seconds=1.0,
        compute=compute,
    )
    # Should return immediately with stale value, while refresh happens in background.
    assert v_stale == {"v": 1}

    await asyncio.wait_for(refreshed.wait(), timeout=1.0)

    v2 = await get_or_compute(
        key,
        expected_type=dict,
        ttl_seconds=0.01,
        stale_seconds=1.0,
        compute=compute,
    )
    assert v2 == {"v": 2}
    assert calls == 2

