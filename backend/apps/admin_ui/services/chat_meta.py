from __future__ import annotations

from typing import Any

from backend.domain.candidates.models import ChatMessageDirection


SYSTEM_PAYLOAD_KINDS = {
    "system",
    "workflow",
    "status_change",
    "slot_update",
    "intro_day",
    "service",
}


def derive_chat_message_kind(
    direction: str | None,
    *,
    author_label: str | None = None,
    payload_json: dict[str, Any] | None = None,
) -> str:
    normalized_direction = str(direction or "").strip().lower()
    if normalized_direction == ChatMessageDirection.INBOUND.value:
        return "candidate"

    payload = payload_json if isinstance(payload_json, dict) else {}
    payload_kind = str(
        payload.get("kind")
        or payload.get("event")
        or payload.get("message_kind")
        or ""
    ).strip().lower()
    normalized_author = str(author_label or "").strip().lower()

    if payload_kind in SYSTEM_PAYLOAD_KINDS:
        return "system"
    if normalized_author in {"system", "система", "automation"}:
        return "system"
    if "bot" in normalized_author or normalized_author in {"candidate_max", "max"}:
        return "bot"
    return "recruiter"


def compact_chat_preview(text: str | None, *, fallback: str = "Системное сообщение", limit: int = 140) -> str:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return fallback
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(1, limit - 1)].rstrip() + "…"
