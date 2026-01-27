"""HTTP client for bot-to-backend calls."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Tuple

import aiohttp

from .config import BOT_BACKEND_URL


class BackendClientError(RuntimeError):
    pass


class BackendClient:
    def __init__(self, base_url: Optional[str] = None, *, timeout: float = 10.0) -> None:
        base = (base_url or BOT_BACKEND_URL or "").strip()
        self._base_url = base.rstrip("/")
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base_url)

    async def post_json(self, path: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        if not self._base_url:
            raise BackendClientError("BOT_BACKEND_URL is not configured")

        url = f"{self._base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(url, json=payload) as resp:
                    status = resp.status
                    try:
                        data = await resp.json()
                    except Exception:
                        text = await resp.text()
                        data = {"raw": text}
                    return status, data
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                raise BackendClientError(str(exc)) from exc
