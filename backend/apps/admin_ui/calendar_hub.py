"""Realtime calendar events broadcast (in-memory WebSocket hub)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)

ChangeType = Literal["created", "updated", "deleted"]
PrincipalType = Literal["admin", "recruiter"]


@dataclass(frozen=True)
class CalendarClientScope:
    principal_type: PrincipalType
    principal_id: int
    city_ids: frozenset[int]


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
        self._clients: dict[WebSocket, CalendarClientScope] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _payload_recruiter_id(cls, payload: Dict[str, Any]) -> Optional[int]:
        direct = cls._coerce_int(payload.get("recruiter_id"))
        if direct is not None:
            return direct
        slot = payload.get("slot")
        if not isinstance(slot, dict):
            return None
        extended = slot.get("extendedProps")
        if isinstance(extended, dict):
            nested = cls._coerce_int(extended.get("recruiter_id"))
            if nested is not None:
                return nested
        return cls._coerce_int(slot.get("recruiter_id"))

    @classmethod
    def _payload_city_id(cls, payload: Dict[str, Any]) -> Optional[int]:
        slot = payload.get("slot")
        if not isinstance(slot, dict):
            return None
        extended = slot.get("extendedProps")
        if isinstance(extended, dict):
            nested = cls._coerce_int(extended.get("city_id"))
            if nested is not None:
                return nested
        return cls._coerce_int(slot.get("city_id"))

    @classmethod
    def _is_payload_allowed(cls, scope: CalendarClientScope, payload: Dict[str, Any]) -> bool:
        if scope.principal_type == "admin":
            return True

        recruiter_id = cls._payload_recruiter_id(payload)
        if recruiter_id is not None and recruiter_id == scope.principal_id:
            return True

        city_id = cls._payload_city_id(payload)
        return city_id is not None and city_id in scope.city_ids

    @staticmethod
    def _sanitize_payload_for_recruiter(payload: Dict[str, Any]) -> Dict[str, Any]:
        slot = payload.get("slot")
        if not isinstance(slot, dict):
            return payload

        safe_payload = dict(payload)
        safe_slot = dict(slot)
        extended = safe_slot.get("extendedProps")
        if isinstance(extended, dict):
            allowed_extended_keys = {
                "event_type",
                "slot_id",
                "status",
                "status_label",
                "recruiter_id",
                "recruiter_name",
                "recruiter_tz",
                "city_id",
                "city_name",
                "city_tz",
                "candidate_id",
                "candidate_name",
                "duration_min",
                "local_start",
                "local_end",
                "local_date",
            }
            safe_slot["extendedProps"] = {
                key: value
                for key, value in extended.items()
                if key in allowed_extended_keys
            }

        safe_payload["slot"] = safe_slot
        return safe_payload

    async def connect(
        self,
        ws: WebSocket,
        *,
        principal_type: PrincipalType,
        principal_id: int,
        city_ids: Optional[set[int]] = None,
    ) -> None:
        """Accept and register a new WebSocket client."""
        await ws.accept()
        scope = CalendarClientScope(
            principal_type=principal_type,
            principal_id=principal_id,
            city_ids=frozenset(city_ids or set()),
        )
        async with self._lock:
            self._clients[ws] = scope
        logger.debug(f"Calendar WebSocket client connected. Total: {len(self._clients)}")

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket client from the hub."""
        async with self._lock:
            self._clients.pop(ws, None)
        logger.debug(f"Calendar WebSocket client disconnected. Total: {len(self._clients)}")

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Send a message to all connected clients."""
        if not self._clients:
            return

        stale: list[WebSocket] = []
        for ws, scope in list(self._clients.items()):
            if not self._is_payload_allowed(scope, payload):
                continue
            scoped_payload = (
                payload
                if scope.principal_type == "admin"
                else self._sanitize_payload_for_recruiter(payload)
            )
            try:
                await ws.send_json(scoped_payload)
            except Exception as e:
                logger.debug(f"Failed to send to WebSocket client: {e}")
                stale.append(ws)

        if stale:
            async with self._lock:
                for ws in stale:
                    self._clients.pop(ws, None)

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
