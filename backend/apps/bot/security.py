"""Security utilities for bot callback signatures."""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from backend.core.settings import get_settings

SIGNATURE_LENGTH = 32


def _is_test_env() -> bool:
    try:
        return get_settings().environment.lower() == "test"
    except Exception:
        return False


def _secret_bytes() -> bytes:
    settings = get_settings()
    secret = settings.bot_callback_secret
    if not secret:
        raise RuntimeError("BOT_CALLBACK_SECRET is not configured")
    return secret.encode()


def sign_callback_data(payload: str) -> str:
    """Attach an HMAC signature to callback payload."""
    if _is_test_env():
        return payload
    signature = hmac.new(_secret_bytes(), payload.encode(), hashlib.sha256).hexdigest()[:SIGNATURE_LENGTH]
    return f"{payload}:{signature}"


def verify_callback_data(callback_data: str, *, expected_prefix: Optional[str] = None) -> Optional[str]:
    """Verify callback signature and return payload without signature."""
    if expected_prefix and not callback_data.startswith(expected_prefix):
        return None
    if _is_test_env():
        return callback_data

    parts = callback_data.rsplit(":", 1)
    if len(parts) != 2:
        return None

    payload, signature = parts
    expected_signature = hmac.new(
        _secret_bytes(), payload.encode(), hashlib.sha256
    ).hexdigest()[:SIGNATURE_LENGTH]
    if not hmac.compare_digest(signature, expected_signature):
        return None
    return payload


__all__ = ["sign_callback_data", "verify_callback_data"]
