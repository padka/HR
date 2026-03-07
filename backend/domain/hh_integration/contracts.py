"""Contracts and constants for direct HH integration."""

from __future__ import annotations

from typing import Final

HH_PROVIDER: Final[str] = "hh"

DEFAULT_HH_WEBHOOK_ACTIONS: Final[tuple[str, ...]] = (
    "NEW_RESPONSE_OR_INVITATION_VACANCY",
    "NEGOTIATION_EMPLOYER_STATE_CHANGE",
    "VACANCY_CHANGE",
)


class HHConnectionStatus:
    ACTIVE = "active"
    ERROR = "error"
    REVOKED = "revoked"


class HHWebhookDeliveryStatus:
    RECEIVED = "received"
    PROCESSED = "processed"
    ERROR = "error"


class HHSyncJobStatus:
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    DEAD = "dead"


class HHSyncDirection:
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class HHIdentitySyncStatus:
    LINKED = "linked"
    PENDING = "pending_sync"
    SYNCED = "synced"
    FAILED = "failed_sync"
    CONFLICTED = "conflicted"
    STALE = "stale"
