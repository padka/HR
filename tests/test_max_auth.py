from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import urlencode

import pytest
from backend.apps.admin_api.max_auth import validate_max_init_data

BOT_TOKEN = "max-test-token"


def _generate_max_init_data(
    *,
    user_id: int = 123456,
    bot_token: str = BOT_TOKEN,
    start_param: str | None = "launch_opaque_ref",
    query_id: str = "query-123",
    auth_date: int | None = None,
) -> str:
    payload = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": query_id,
        "user": json.dumps(
            {
                "id": user_id,
                "username": "max_user",
                "first_name": "Max",
                "last_name": "Tester",
                "language_code": "ru",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    if start_param is not None:
        payload["start_param"] = start_param

    launch_params = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    payload["hash"] = hmac.new(
        secret_key,
        launch_params.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(payload)


def test_validate_max_init_data_accepts_valid_payload():
    init_data = _generate_max_init_data()

    validated = validate_max_init_data(init_data, BOT_TOKEN)

    assert validated.user.user_id == 123456
    assert validated.user.username == "max_user"
    assert validated.query_id == "query-123"
    assert validated.start_param == "launch_opaque_ref"


def test_validate_max_init_data_rejects_duplicate_keys():
    init_data = _generate_max_init_data() + "&query_id=duplicate"

    with pytest.raises(ValueError, match="Duplicate 'query_id' field"):
        validate_max_init_data(init_data, BOT_TOKEN)


def test_validate_max_init_data_rejects_stale_payload():
    init_data = _generate_max_init_data(auth_date=int(time.time()) - 86500)

    with pytest.raises(ValueError, match="too old"):
        validate_max_init_data(init_data, BOT_TOKEN, max_age_seconds=86400)


def test_validate_max_init_data_success_logs_without_user_id(caplog: pytest.LogCaptureFixture):
    init_data = _generate_max_init_data(user_id=998877)
    caplog.set_level(logging.DEBUG, logger="backend.apps.admin_api.max_auth")

    validate_max_init_data(init_data, BOT_TOKEN)

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "Validated MAX initData" in messages
    assert "998877" not in messages
