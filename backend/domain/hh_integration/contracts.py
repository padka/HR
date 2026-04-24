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
    FORBIDDEN = "forbidden"


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


class HHSyncFailureCode:
    TRANSPORT_ERROR = "transport_error"
    PROVIDER_HTTP_ERROR = "provider_http_error"
    ACCESS_FORBIDDEN = "hh_access_forbidden"
    RATE_LIMITED = "hh_rate_limited"
    NOT_FOUND = "hh_not_found"
    TOKEN_REFRESH_REQUIRED = "token_refresh_required"
    ACTION_UNAVAILABLE = "action_unavailable"
    WRONG_STATE = "wrong_state"
    IDENTITY_NOT_LINKED = "identity_not_linked"
