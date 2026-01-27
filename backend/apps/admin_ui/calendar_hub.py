"""Realtime calendar events broadcast (in-memory WebSocket hub)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)

ChangeType = Literal["created", "updated", "deleted"]


class CalendarHub:
    """
    WebSocket hub for broadcasting calendar/slot changes in real-time.

    Usage:
        # On slot creation
        await calendar_hub.notify_slot_change(slot.id, "created", slot_data)

        # On slot update (reschedule, status change)
        await calendar_hub.notify_slot_change(slot.id, "updated", slot_data)

        # On slot deletion
        await calendar_hub.notify_slot_change(slot.id, "deleted", {"id": slot.id})
    """

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a new WebSocket client."""
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        logger.debug(f"Calendar WebSocket client connected. Total: {len(self._clients)}")

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket client from the hub."""
        async with self._lock:
            self._clients.discard(ws)
        logger.debug(f"Calendar WebSocket client disconnected. Total: {len(self._clients)}")

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Send a message to all connected clients."""
        if not self._clients:
            return

        stale: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.debug(f"Failed to send to WebSocket client: {e}")
                stale.append(ws)

        if stale:
            async with self._lock:
                for ws in stale:
                    self._clients.discard(ws)

    async def notify_slot_change(
        self,
        slot_id: int,
        change_type: ChangeType,
        slot_data: Dict[str, Any],
        *,
        recruiter_id: Optional[int] = None,
    ) -> None:
        """
        Broadcast a slot change event to all connected clients.

        Args:
            slot_id: The ID of the slot that changed
            change_type: Type of change ('created', 'updated', 'deleted')
            slot_data: Slot data in FullCalendar event format
            recruiter_id: Optional recruiter ID for filtering on client side
        """
        await self.broadcast({
            "type": "slot_change",
            "change_type": change_type,
            "slot_id": slot_id,
            "recruiter_id": recruiter_id,
            "slot": slot_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @property
    def client_count(self) -> int:
        """Return the number of connected clients."""
        return len(self._clients)


# Global singleton instance
calendar_hub = CalendarHub()


# Convenience functions for use in services
async def notify_slot_created(
    slot_id: int,
    slot_data: Dict[str, Any],
    recruiter_id: Optional[int] = None,
) -> None:
    """Notify clients that a slot was created."""
    await calendar_hub.notify_slot_change(slot_id, "created", slot_data, recruiter_id=recruiter_id)


async def notify_slot_updated(
    slot_id: int,
    slot_data: Dict[str, Any],
    recruiter_id: Optional[int] = None,
) -> None:
    """Notify clients that a slot was updated."""
    await calendar_hub.notify_slot_change(slot_id, "updated", slot_data, recruiter_id=recruiter_id)


async def notify_slot_deleted(
    slot_id: int,
    recruiter_id: Optional[int] = None,
) -> None:
    """Notify clients that a slot was deleted."""
    await calendar_hub.notify_slot_change(
        slot_id,
        "deleted",
        {"id": slot_id},
        recruiter_id=recruiter_id,
    )
