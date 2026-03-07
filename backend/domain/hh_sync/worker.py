"""Worker for processing hh.ru outbox entries via n8n webhooks."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from backend.domain.hh_sync.models import HHSyncLog
from backend.domain.models import OutboxNotification

log = logging.getLogger(__name__)

# n8n webhook URLs (configured via env)
_N8N_HH_SYNC_URL = os.getenv("N8N_HH_SYNC_WEBHOOK_URL", "")
_N8N_HH_RESOLVE_URL = os.getenv("N8N_HH_RESOLVE_WEBHOOK_URL", "")
_HH_WEBHOOK_SECRET = os.getenv("HH_WEBHOOK_SECRET", "")
_HH_WEBHOOK_TIMEOUT = 15  # seconds


async def process_hh_outbox_entry(
    entry: OutboxNotification,
    *,
    session=None,
) -> bool:
    """Send an hh.ru outbox entry to the appropriate n8n webhook.

    Args:
        entry: The OutboxNotification to process.
        session: SQLAlchemy async session for updating audit log.

    Returns:
        True if the webhook call succeeded, False otherwise.
    """
    if entry.type == "hh_status_sync":
        url = _N8N_HH_SYNC_URL
    elif entry.type == "hh_resolve_negotiation":
        url = _N8N_HH_RESOLVE_URL
    else:
        log.warning("hh_worker: unknown outbox type=%s id=%s", entry.type, entry.id)
        return False

    if not url:
        log.error(
            "hh_worker: no webhook URL configured for type=%s (check env vars)",
            entry.type,
        )
        return False

    headers = {
        "Content-Type": "application/json",
    }
    if _HH_WEBHOOK_SECRET:
        headers["X-Webhook-Secret"] = _HH_WEBHOOK_SECRET

    try:
        async with httpx.AsyncClient(timeout=_HH_WEBHOOK_TIMEOUT) as client:
            resp = await client.post(
                url,
                json=entry.payload_json,
                headers=headers,
            )
            resp.raise_for_status()

        log.info(
            "hh_worker: webhook OK type=%s outbox=%s status=%s",
            entry.type,
            entry.id,
            resp.status_code,
        )
        return True

    except httpx.HTTPStatusError as exc:
        error_msg = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        log.error("hh_worker: webhook failed type=%s outbox=%s: %s", entry.type, entry.id, error_msg)
        if session is not None:
            await _log_error(session, entry, error_msg)
        return False

    except httpx.RequestError as exc:
        error_msg = f"Request error: {exc}"
        log.error("hh_worker: webhook failed type=%s outbox=%s: %s", entry.type, entry.id, error_msg)
        if session is not None:
            await _log_error(session, entry, error_msg)
        return False


async def _log_error(session, entry: OutboxNotification, error_msg: str) -> None:
    """Write the error to candidate's hh_sync fields and sync log."""
    candidate_id = (entry.payload_json or {}).get("candidate_id")
    if not candidate_id:
        return

    from backend.domain.candidates.models import User

    from sqlalchemy import select as sa_select

    result = await session.execute(
        sa_select(User).where(User.id == candidate_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.hh_sync_status = "error"
        user.hh_sync_error = error_msg[:500]


async def handle_sync_callback(
    *,
    candidate_id: int,
    success: bool,
    hh_status: Optional[str] = None,
    error_message: Optional[str] = None,
    response_payload: Optional[dict] = None,
    session,
) -> None:
    """Handle callback from n8n after hh.ru API call.

    Updates the candidate's sync status and writes to the audit log.
    """
    from backend.domain.candidates.models import User
    from sqlalchemy import select as sa_select
    from datetime import datetime, timezone

    result = await session.execute(
        sa_select(User).where(User.id == candidate_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        log.warning("hh_callback: candidate_id=%s not found", candidate_id)
        return

    if success:
        user.hh_sync_status = "synced"
        user.hh_sync_error = None
        user.hh_synced_at = datetime.now(timezone.utc)
    else:
        user.hh_sync_status = "error"
        user.hh_sync_error = (error_message or "Unknown error")[:500]

    # Update the most recent pending audit log entry
    from sqlalchemy import desc

    log_result = await session.execute(
        sa_select(HHSyncLog)
        .where(
            HHSyncLog.candidate_id == candidate_id,
            HHSyncLog.status == "pending",
        )
        .order_by(desc(HHSyncLog.created_at))
        .limit(1)
    )
    sync_log = log_result.scalar_one_or_none()
    if sync_log:
        sync_log.status = "success" if success else "error"
        sync_log.response_payload = response_payload
        sync_log.error_message = error_message

    await session.flush()
    log.info(
        "hh_callback: candidate=%s success=%s hh_status=%s",
        candidate_id,
        success,
        hh_status,
    )


async def handle_resolve_callback(
    *,
    candidate_id: int,
    negotiation_id: Optional[str] = None,
    vacancy_id: Optional[str] = None,
    not_found: bool = False,
    error_message: Optional[str] = None,
    response_payload: Optional[dict] = None,
    session,
) -> None:
    """Handle callback from n8n after negotiation resolve attempt.

    Links the candidate to their hh.ru negotiation if found.
    """
    from backend.domain.candidates.models import User
    from sqlalchemy import select as sa_select, desc

    result = await session.execute(
        sa_select(User).where(User.id == candidate_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        log.warning("hh_resolve_callback: candidate_id=%s not found", candidate_id)
        return

    if negotiation_id and not not_found:
        user.hh_negotiation_id = negotiation_id
        user.hh_vacancy_id = vacancy_id
        user.hh_sync_status = "synced"
        user.hh_sync_error = None
        log.info(
            "hh_resolve_callback: linked candidate=%s to negotiation=%s vacancy=%s",
            candidate_id,
            negotiation_id,
            vacancy_id,
        )
    elif not_found:
        user.hh_sync_status = "skipped"
        user.hh_sync_error = "Negotiation not found for this resume"
        log.info("hh_resolve_callback: no negotiation found for candidate=%s", candidate_id)
    else:
        user.hh_sync_status = "error"
        user.hh_sync_error = (error_message or "Resolve failed")[:500]

    # Update audit log
    log_result = await session.execute(
        sa_select(HHSyncLog)
        .where(
            HHSyncLog.candidate_id == candidate_id,
            HHSyncLog.event_type == "resolve_negotiation",
            HHSyncLog.status == "pending",
        )
        .order_by(desc(HHSyncLog.created_at))
        .limit(1)
    )
    sync_log = log_result.scalar_one_or_none()
    if sync_log:
        sync_log.status = "success" if (negotiation_id and not not_found) else ("skipped" if not_found else "error")
        sync_log.response_payload = response_payload
        sync_log.error_message = error_message

    await session.flush()


__all__ = [
    "process_hh_outbox_entry",
    "handle_sync_callback",
    "handle_resolve_callback",
]
