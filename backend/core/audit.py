from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from fastapi import Request

from backend.core.db import async_session
from backend.domain.models import AuditLog

logger = logging.getLogger(__name__)


@dataclass
class AuditContext:
    """Context captured for audit logging."""

    username: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


_ctx_var: ContextVar[Optional[AuditContext]] = ContextVar("audit_ctx", default=None)


def set_audit_context(ctx: Optional[AuditContext]) -> None:
    """Persist audit context for the current async task."""
    _ctx_var.set(ctx)


def _build_context_from_request(request: Optional[Request]) -> AuditContext:
    username = None
    ip_address = None
    user_agent = None
    if request is not None:
        username = getattr(getattr(request, "state", None), "admin_username", None)
        ip_address = request.client.host if request and request.client else None
        user_agent = request.headers.get("user-agent")
    return AuditContext(username=username, ip_address=ip_address, user_agent=user_agent)


def get_audit_context(request: Optional[Request] = None) -> AuditContext:
    """Return the current audit context or build a fallback from request."""
    ctx = _ctx_var.get()
    if ctx:
        return ctx
    ctx = _build_context_from_request(request)
    _ctx_var.set(ctx)
    return ctx


def _normalize_changes(changes: Optional[Mapping[str, Any]]) -> Optional[dict]:
    if not changes:
        return None
    try:
        return json.loads(json.dumps(changes))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to serialise audit changes: %s", exc)
        return {"_unserializable": str(changes)}


async def log_audit_action(
    action: str,
    entity_type: Optional[str],
    entity_id: Optional[str | int],
    *,
    changes: Optional[Mapping[str, Any]] = None,
    ctx: Optional[AuditContext] = None,
) -> None:
    """Persist a structured audit event."""

    context = ctx or get_audit_context()
    entity_value = str(entity_id) if entity_id is not None else None
    record = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_value,
        username=context.username,
        ip_address=context.ip_address,
        user_agent=context.user_agent,
        changes=_normalize_changes(changes),
    )

    try:
        async with async_session() as session:
            session.add(record)
            await session.commit()
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Failed to write audit log", exc_info=exc)


__all__ = ["AuditContext", "log_audit_action", "get_audit_context", "set_audit_context"]
