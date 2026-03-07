"""Parse hh.ru resume URLs and resolve negotiation IDs via n8n webhook."""

from __future__ import annotations

import logging
import re
from typing import Optional

from backend.domain.hh_sync.models import HHSyncLog

log = logging.getLogger(__name__)

# Matches URLs like:
#   https://hh.ru/resume/abc123def456
#   https://hh.ru/resume/abc123def456?from=search
#   https://spb.hh.ru/resume/abc123def456
_HH_RESUME_URL_RE = re.compile(
    r"https?://(?:\w+\.)?hh\.ru/resume/([a-zA-Z0-9]+)",
)


def parse_resume_id(url: str) -> Optional[str]:
    """Extract resume_id from an hh.ru resume URL.

    Args:
        url: Full hh.ru resume URL.

    Returns:
        The resume hash/ID string, or None if the URL doesn't match.
    """
    if not url:
        return None
    m = _HH_RESUME_URL_RE.search(url.strip())
    return m.group(1) if m else None


async def request_resolve_negotiation(
    *,
    resume_id: str,
    candidate_id: int,
    n8n_webhook_url: str,
    webhook_secret: str,
    session=None,
) -> Optional[int]:
    """Fire an async HTTP request to n8n to resolve a negotiation by resume_id.

    Creates an OutboxNotification so the resolve request is retried on failure.

    Args:
        resume_id: hh.ru resume identifier.
        candidate_id: Internal candidate (users.id).
        n8n_webhook_url: URL of the n8n resolve webhook.
        webhook_secret: HMAC secret for authenticating the webhook.
        session: SQLAlchemy async session (if provided, writes outbox entry).

    Returns:
        The outbox notification ID if created, else None.
    """
    from backend.domain.models import OutboxNotification  # avoid circular import

    payload = {
        "resume_id": resume_id,
        "candidate_id": candidate_id,
    }

    if session is not None:
        outbox = OutboxNotification(
            type="hh_resolve_negotiation",
            payload_json=payload,
            status="pending",
        )
        session.add(outbox)
        # Also write an audit log entry
        sync_log = HHSyncLog(
            candidate_id=candidate_id,
            event_type="resolve_negotiation",
            status="pending",
            request_payload=payload,
        )
        session.add(sync_log)
        await session.flush()
        log.info(
            "hh_resolve: queued outbox=%s for candidate=%s resume=%s",
            outbox.id,
            candidate_id,
            resume_id,
        )
        return outbox.id

    return None


__all__ = [
    "parse_resume_id",
    "request_resolve_negotiation",
]
