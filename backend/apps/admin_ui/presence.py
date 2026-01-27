"""Realtime recruiter presence broadcast (in-memory)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class PresenceHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        if not self._clients:
            return
        stale: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        if stale:
            async with self._lock:
                for ws in stale:
                    self._clients.discard(ws)


presence_hub = PresenceHub()


async def notify_recruiter_presence(
    recruiter_id: int,
    *,
    is_online: bool,
    last_seen_at: Optional[datetime],
) -> None:
    await presence_hub.broadcast(
        {
            "type": "recruiter_presence",
            "recruiter_id": recruiter_id,
            "is_online": is_online,
            "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
        }
    )
