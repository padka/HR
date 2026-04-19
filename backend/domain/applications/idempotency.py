from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


def scoped_idempotency_key(producer_family: str, idempotency_key: str) -> str:
    producer = producer_family.strip().lower()
    key = idempotency_key.strip()
    if not producer:
        raise ValueError("producer_family is required for idempotency scoping")
    if not key:
        raise ValueError("idempotency_key cannot be blank")
    return f"{producer}:{key}"


def canonicalize_payload(payload: dict[str, Any]) -> str:
    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [normalize(item) for item in value]
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.isoformat()
            return value.astimezone().isoformat()
        return value

    return json.dumps(normalize(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint_payload(payload: dict[str, Any]) -> str:
    encoded = canonicalize_payload(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_resolver_idempotency_key(
    *,
    candidate_id: int,
    producer_family: str,
    source_ref: str,
    signal: str,
    requisition_id: int | None,
) -> str:
    raw = f"{signal}:{candidate_id}:{requisition_id or 'null'}:{source_ref.strip()}"
    return scoped_idempotency_key(producer_family, raw)
