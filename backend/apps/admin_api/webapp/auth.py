"""Telegram WebApp authentication and initData validation.

This module implements secure validation of Telegram WebApp initData
according to Telegram's official documentation.

Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hmac
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qsl, unquote

from fastapi import Depends, HTTPException, Header, status

logger = logging.getLogger(__name__)


@dataclass
class TelegramUser:
    """Telegram user data extracted from initData."""

    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: bool = False
    auth_date: int = 0
    hash: str = ""

    @property
    def full_name(self) -> str:
        """Get full name of the user."""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) or self.username or str(self.user_id)


def _parse_user_from_init_data(init_data: str) -> dict:
    """Parse user data from initData query string.

    Args:
        init_data: Raw initData string from Telegram WebApp

    Returns:
        Dict with parsed user data
    """
    params = dict(parse_qsl(init_data))

    # Parse user JSON (if present)
    user_json = params.get("user")
    if not user_json:
        raise ValueError("Missing 'user' field in initData")

    # Telegram sends user as JSON string
    import json

    try:
        user_data = json.loads(unquote(user_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid user JSON: {exc}") from exc

    return {
        "user_id": int(user_data.get("id", 0)),
        "username": user_data.get("username"),
        "first_name": user_data.get("first_name"),
        "last_name": user_data.get("last_name"),
        "language_code": user_data.get("language_code"),
        "is_premium": user_data.get("is_premium", False),
        "auth_date": int(params.get("auth_date", 0)),
        "hash": params.get("hash", ""),
    }


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> TelegramUser:
    """Validate Telegram WebApp initData signature.

    This function validates that the initData was indeed sent by Telegram
    and has not been tampered with.

    Args:
        init_data: Raw initData string from Telegram WebApp
        bot_token: Telegram bot token for validation
        max_age_seconds: Maximum age of initData in seconds (default: 24h)

    Returns:
        TelegramUser object with validated user data

    Raises:
        ValueError: If validation fails

    Reference:
        https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        raise ValueError("initData is empty")

    if not bot_token:
        raise ValueError("bot_token is empty")

    # Parse initData as query string
    params = dict(parse_qsl(init_data))

    # Extract hash from params
    received_hash = params.pop("hash", None)
    if not received_hash:
        raise ValueError("Missing 'hash' field in initData")

    # Check auth_date (timestamp)
    auth_date = params.get("auth_date")
    if not auth_date:
        raise ValueError("Missing 'auth_date' field in initData")

    try:
        auth_timestamp = int(auth_date)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid auth_date: {exc}") from exc

    # Check initData age
    import time

    current_timestamp = int(time.time())
    age_seconds = current_timestamp - auth_timestamp

    if age_seconds > max_age_seconds:
        raise ValueError(f"initData is too old (age: {age_seconds}s, max: {max_age_seconds}s)")

    if age_seconds < -60:  # Allow 60s clock skew
        raise ValueError(f"initData is from the future (age: {age_seconds}s)")

    # Build data_check_string
    # Format: key=value pairs, sorted alphabetically by key, joined with \n
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )

    # Compute secret key
    # secret_key = HMAC_SHA256(<bot_token>, "WebAppData")
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    # Compute hash
    # hash = HMAC_SHA256(secret_key, data_check_string)
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Compare hashes (constant-time comparison)
    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("Invalid initData signature")

    # Parse user data
    user_data = _parse_user_from_init_data(init_data)
    if not user_data.get("user_id"):
        raise ValueError("Missing or invalid user_id")

    logger.info(
        "Validated initData for user %d (age: %ds)",
        user_data["user_id"],
        age_seconds,
    )

    return TelegramUser(**user_data)


class TelegramWebAppAuth:
    """FastAPI dependency for Telegram WebApp authentication."""

    def __init__(self, *, bot_token: Optional[str] = None, max_age_seconds: int = 86400):
        """Initialize auth dependency.

        Args:
            bot_token: Telegram bot token (if None, will be fetched from config)
            max_age_seconds: Maximum age of initData (default: 24h)
        """
        self._bot_token = bot_token
        self._max_age_seconds = max_age_seconds

    async def __call__(
        self,
        x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    ) -> TelegramUser:
        """Validate initData from HTTP header.

        Args:
            x_telegram_init_data: initData from X-Telegram-Init-Data header

        Returns:
            TelegramUser object

        Raises:
            HTTPException: If validation fails (401 Unauthorized)
        """
        bot_token = self._bot_token
        if not bot_token:
            # Fetch bot token from config/env
            from backend.apps.bot.config import get_bot_token

            bot_token = get_bot_token()

        try:
            return validate_init_data(
                x_telegram_init_data,
                bot_token,
                max_age_seconds=self._max_age_seconds,
            )
        except ValueError as exc:
            logger.warning("initData validation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Telegram WebApp initData: {exc}",
            ) from exc


def get_telegram_webapp_auth(max_age_seconds: int = 86400) -> TelegramWebAppAuth:
    """Factory for TelegramWebAppAuth dependency.

    Usage:
        @router.get("/api/webapp/me")
        async def get_me(user: TelegramUser = Depends(get_telegram_webapp_auth())):
            return {"user_id": user.user_id, "name": user.full_name}
    """
    return TelegramWebAppAuth(max_age_seconds=max_age_seconds)


__all__ = ["TelegramUser", "TelegramWebAppAuth", "validate_init_data", "get_telegram_webapp_auth"]
