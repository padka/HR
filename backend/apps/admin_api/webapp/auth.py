"""Telegram and MAX WebApp authentication and initData validation.

This module implements secure validation of WebApp initData / WebAppData
according to the provider HMAC validation model.

References:
- https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
- https://dev.max.ru/docs/webapps/validation
"""

from __future__ import annotations

import json
import hmac
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional
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


@dataclass
class MaxWebAppUser:
    """MAX WebApp user data extracted from WebAppData."""

    user_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    auth_date: int = 0
    hash: str = ""
    query_id: Optional[str] = None
    start_param: Optional[str] = None

    @property
    def full_name(self) -> str:
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) or self.username or str(self.user_id)


def _parse_webapp_params(init_data: str) -> dict[str, str]:
    params = dict(parse_qsl(init_data, keep_blank_values=True))
    if not params:
        raise ValueError("initData is empty")
    return params


def _load_user_json_from_params(params: dict[str, str]) -> dict[str, Any]:
    user_json = params.get("user")
    if not user_json:
        raise ValueError("Missing 'user' field in initData")

    try:
        return json.loads(unquote(user_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid user JSON: {exc}") from exc


def _parse_user_from_init_data(init_data: str) -> dict:
    """Parse user data from initData query string.

    Args:
        init_data: Raw initData string from Telegram WebApp

    Returns:
        Dict with parsed user data
    """
    params = _parse_webapp_params(init_data)
    user_data = _load_user_json_from_params(params)

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


def _validate_signed_webapp_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int,
) -> tuple[dict[str, str], str, int]:
    if not init_data:
        raise ValueError("initData is empty")

    if not bot_token:
        raise ValueError("bot_token is empty")

    params = _parse_webapp_params(init_data)
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

    current_timestamp = int(time.time())
    age_seconds = current_timestamp - auth_timestamp

    if age_seconds > max_age_seconds:
        raise ValueError(f"initData is too old (age: {age_seconds}s, max: {max_age_seconds}s)")

    if age_seconds < -60:  # Allow 60s clock skew
        raise ValueError(f"initData is from the future (age: {age_seconds}s)")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("Invalid initData signature")

    return params, received_hash, age_seconds


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> TelegramUser:
    """Validate Telegram WebApp initData signature."""
    _, received_hash, age_seconds = _validate_signed_webapp_data(
        init_data,
        bot_token,
        max_age_seconds=max_age_seconds,
    )
    user_data = _parse_user_from_init_data(init_data)
    if not user_data.get("user_id"):
        raise ValueError("Missing or invalid user_id")
    user_data["hash"] = received_hash

    logger.info(
        "Validated initData for user %d (age: %ds)",
        user_data["user_id"],
        age_seconds,
    )

    return TelegramUser(**user_data)


def validate_max_webapp_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 900,
) -> MaxWebAppUser:
    """Validate MAX WebAppData signature and extract normalized user context."""

    params, received_hash, age_seconds = _validate_signed_webapp_data(
        init_data,
        bot_token,
        max_age_seconds=max_age_seconds,
    )
    user_data = _load_user_json_from_params({**params, "hash": received_hash})
    user_id = str(user_data.get("id") or user_data.get("user_id") or "").strip()
    if not user_id:
        raise ValueError("Missing or invalid user_id")

    max_user = MaxWebAppUser(
        user_id=user_id,
        username=user_data.get("username"),
        first_name=user_data.get("first_name"),
        last_name=user_data.get("last_name"),
        language_code=user_data.get("language_code"),
        auth_date=int(params.get("auth_date", 0)),
        hash=received_hash,
        query_id=str(params.get("query_id") or "").strip() or None,
        start_param=str(
            params.get("start_param")
            or params.get("startapp")
            or params.get("payload")
            or ""
        ).strip() or None,
    )
    logger.info(
        "Validated MAX WebAppData for user %s (age: %ds)",
        max_user.user_id,
        age_seconds,
    )
    return max_user


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
            from backend.core.settings import get_settings

            bot_token = get_settings().bot_token
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Telegram bot token is not configured",
            )

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


class MaxWebAppAuth:
    """FastAPI dependency for MAX WebAppData validation."""

    def __init__(self, *, bot_token: Optional[str] = None, max_age_seconds: int = 900):
        self._bot_token = bot_token
        self._max_age_seconds = max_age_seconds

    async def __call__(
        self,
        x_max_webapp_data: str = Header(..., alias="X-Max-WebApp-Data"),
    ) -> MaxWebAppUser:
        bot_token = self._bot_token
        if not bot_token:
            from backend.core.settings import get_settings

            bot_token = get_settings().max_bot_token
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MAX bot token is not configured",
            )

        try:
            return validate_max_webapp_data(
                x_max_webapp_data,
                bot_token,
                max_age_seconds=self._max_age_seconds,
            )
        except ValueError as exc:
            logger.warning("MAX WebAppData validation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid MAX WebAppData: {exc}",
            ) from exc


def get_max_webapp_auth(max_age_seconds: int = 900) -> MaxWebAppAuth:
    return MaxWebAppAuth(max_age_seconds=max_age_seconds)


__all__ = [
    "TelegramUser",
    "MaxWebAppUser",
    "TelegramWebAppAuth",
    "MaxWebAppAuth",
    "validate_init_data",
    "validate_max_webapp_data",
    "get_telegram_webapp_auth",
    "get_max_webapp_auth",
]
