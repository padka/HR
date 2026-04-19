"""MAX mini-app authentication and initData validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote_plus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MaxUser:
    """MAX user data extracted from initData."""

    user_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None

    @property
    def full_name(self) -> str:
        parts = [part for part in (self.first_name, self.last_name) if part]
        return " ".join(parts) or self.username or str(self.user_id)


@dataclass(frozen=True)
class MaxInitData:
    """Validated MAX launch payload."""

    user: MaxUser
    query_id: str
    auth_date: int
    hash: str
    start_param: str | None = None
    raw_params: dict[str, str] | None = None


def _parse_init_data_pairs(init_data: str) -> list[tuple[str, str]]:
    raw = str(init_data or "").strip()
    if not raw:
        raise ValueError("initData is empty")

    pairs: list[tuple[str, str]] = []
    seen_keys: set[str] = set()
    for fragment in raw.split("&"):
        if not fragment:
            raise ValueError("Malformed initData")
        key, separator, value = fragment.partition("=")
        if not separator:
            raise ValueError("Malformed initData")
        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("Malformed initData")
        if normalized_key in seen_keys:
            raise ValueError(f"Duplicate '{normalized_key}' field in initData")
        seen_keys.add(normalized_key)
        pairs.append((normalized_key, unquote_plus(value)))
    return pairs


def _parse_init_data_params(init_data: str) -> dict[str, str]:
    pairs = _parse_init_data_pairs(init_data)
    params = {key: value for key, value in pairs}
    if not params:
        raise ValueError("initData is empty")
    return params


def _load_user_json_from_params(params: dict[str, str]) -> dict[str, Any]:
    raw_user_json = params.get("user")
    if not raw_user_json:
        raise ValueError("Missing 'user' field in initData")

    try:
        user_data = json.loads(raw_user_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid user JSON: {exc}") from exc
    if not isinstance(user_data, dict):
        raise ValueError("Invalid user JSON")
    return user_data


def _validate_signed_webapp_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int,
) -> tuple[dict[str, str], str, int]:
    if not bot_token:
        raise ValueError("bot_token is empty")

    params = _parse_init_data_params(init_data)
    received_hash = params.pop("hash", None)
    if not received_hash:
        raise ValueError("Missing 'hash' field in initData")

    auth_date = params.get("auth_date")
    if not auth_date:
        raise ValueError("Missing 'auth_date' field in initData")

    query_id = params.get("query_id")
    if not query_id:
        raise ValueError("Missing 'query_id' field in initData")

    try:
        auth_timestamp = int(auth_date)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid auth_date: {exc}") from exc

    current_timestamp = int(time.time())
    age_seconds = current_timestamp - auth_timestamp
    if age_seconds > max_age_seconds:
        raise ValueError(
            f"initData is too old (age: {age_seconds}s, max: {max_age_seconds}s)"
        )
    if age_seconds < -60:
        raise ValueError(f"initData is from the future (age: {age_seconds}s)")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
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


def validate_max_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> MaxInitData:
    """Validate MAX mini-app initData using the official WebAppData algorithm."""

    params, received_hash, age_seconds = _validate_signed_webapp_data(
        init_data,
        bot_token,
        max_age_seconds=max_age_seconds,
    )
    user_data = _load_user_json_from_params(params)
    try:
        user_id = int(user_data.get("id", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid user id: {exc}") from exc
    if not user_id:
        raise ValueError("Missing or invalid user id")

    validated = MaxInitData(
        user=MaxUser(
            user_id=user_id,
            username=user_data.get("username"),
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name"),
            language_code=user_data.get("language_code"),
        ),
        query_id=str(params.get("query_id") or "").strip(),
        auth_date=int(params.get("auth_date", "0")),
        hash=received_hash,
        start_param=(str(params.get("start_param") or "").strip() or None),
        raw_params=params,
    )
    logger.debug("Validated MAX initData (age: %ss)", age_seconds)
    return validated


__all__ = ["MaxInitData", "MaxUser", "validate_max_init_data"]
