"""Tests for Telegram WebApp initData validation."""

from __future__ import annotations

import time
import hmac
import hashlib
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

from backend.apps.admin_api.webapp.auth import (
    TelegramUser,
    validate_init_data,
    _parse_user_from_init_data,
)


def _generate_valid_init_data(
    user_id: int,
    bot_token: str,
    username: str = "testuser",
    first_name: str = "Test",
    auth_date: Optional[int] = None,
) -> str:
    """Generate valid initData for testing."""
    import json

    if auth_date is None:
        auth_date = int(time.time())

    user_json = json.dumps(
        {
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "language_code": "en",
        }
    )

    params = {
        "user": user_json,
        "auth_date": str(auth_date),
        "query_id": "test_query_id",
    }

    # Build data_check_string
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))

    # Compute secret_key
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    # Compute hash
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    params["hash"] = computed_hash

    return urlencode(params)


class TestParseUserFromInitData:
    """Test _parse_user_from_init_data function."""

    def test_parse_valid_user_data(self):
        """Test parsing valid user data."""
        import json

        user_json = json.dumps(
            {
                "id": 12345,
                "username": "testuser",
                "first_name": "Test",
                "last_name": "User",
                "language_code": "en",
            }
        )
        init_data = urlencode(
            {
                "user": user_json,
                "auth_date": "1234567890",
                "hash": "dummy_hash",
            }
        )

        result = _parse_user_from_init_data(init_data)

        assert result["user_id"] == 12345
        assert result["username"] == "testuser"
        assert result["first_name"] == "Test"
        assert result["last_name"] == "User"
        assert result["language_code"] == "en"
        assert result["auth_date"] == 1234567890
        assert result["hash"] == "dummy_hash"

    def test_parse_missing_user_field(self):
        """Test that missing 'user' field raises ValueError."""
        init_data = urlencode({"auth_date": "1234567890", "hash": "dummy_hash"})

        with pytest.raises(ValueError, match="Missing 'user' field"):
            _parse_user_from_init_data(init_data)

    def test_parse_invalid_user_json(self):
        """Test that invalid user JSON raises ValueError."""
        init_data = urlencode(
            {
                "user": "not a valid json",
                "auth_date": "1234567890",
                "hash": "dummy_hash",
            }
        )

        with pytest.raises(ValueError, match="Invalid user JSON"):
            _parse_user_from_init_data(init_data)


class TestValidateInitData:
    """Test validate_init_data function."""

    def test_validate_valid_init_data(self):
        """Test validation of correctly signed initData."""
        bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        user_id = 12345

        init_data = _generate_valid_init_data(
            user_id=user_id,
            bot_token=bot_token,
            username="testuser",
            first_name="Test",
        )

        user = validate_init_data(init_data, bot_token)

        assert user.user_id == user_id
        assert user.username == "testuser"
        assert user.first_name == "Test"

    def test_validate_empty_init_data(self):
        """Test that empty initData raises ValueError."""
        with pytest.raises(ValueError, match="initData is empty"):
            validate_init_data("", "bot_token")

    def test_validate_empty_bot_token(self):
        """Test that empty bot_token raises ValueError."""
        with pytest.raises(ValueError, match="bot_token is empty"):
            validate_init_data("init_data=test", "")

    def test_validate_missing_hash(self):
        """Test that missing hash raises ValueError."""
        init_data = urlencode({"user": '{"id": 123}', "auth_date": "1234567890"})

        with pytest.raises(ValueError, match="Missing 'hash' field"):
            validate_init_data(init_data, "bot_token")

    def test_validate_missing_auth_date(self):
        """Test that missing auth_date raises ValueError."""
        init_data = urlencode({"user": '{"id": 123}', "hash": "dummy_hash"})

        with pytest.raises(ValueError, match="Missing 'auth_date' field"):
            validate_init_data(init_data, "bot_token")

    def test_validate_invalid_auth_date(self):
        """Test that invalid auth_date raises ValueError."""
        init_data = urlencode(
            {
                "user": '{"id": 123}',
                "auth_date": "not_a_number",
                "hash": "dummy_hash",
            }
        )

        with pytest.raises(ValueError, match="Invalid auth_date"):
            validate_init_data(init_data, "bot_token")

    def test_validate_expired_init_data(self):
        """Test that expired initData raises ValueError."""
        bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        old_auth_date = int(time.time()) - 90000  # 25 hours ago

        init_data = _generate_valid_init_data(
            user_id=12345,
            bot_token=bot_token,
            auth_date=old_auth_date,
        )

        with pytest.raises(ValueError, match="initData is too old"):
            validate_init_data(init_data, bot_token, max_age_seconds=86400)

    def test_validate_future_init_data(self):
        """Test that future initData raises ValueError."""
        bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        future_auth_date = int(time.time()) + 3600  # 1 hour in the future

        init_data = _generate_valid_init_data(
            user_id=12345,
            bot_token=bot_token,
            auth_date=future_auth_date,
        )

        with pytest.raises(ValueError, match="initData is from the future"):
            validate_init_data(init_data, bot_token)

    def test_validate_tampered_init_data(self):
        """Test that tampered initData fails validation."""
        bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

        init_data = _generate_valid_init_data(
            user_id=12345,
            bot_token=bot_token,
        )

        # Tamper with the data
        tampered_init_data = init_data.replace("testuser", "hacker")

        with pytest.raises(ValueError, match="Invalid initData signature"):
            validate_init_data(tampered_init_data, bot_token)

    def test_validate_wrong_bot_token(self):
        """Test that wrong bot_token fails validation."""
        correct_bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        wrong_bot_token = "123456:WRONG-TOKEN"

        init_data = _generate_valid_init_data(
            user_id=12345,
            bot_token=correct_bot_token,
        )

        with pytest.raises(ValueError, match="Invalid initData signature"):
            validate_init_data(init_data, wrong_bot_token)

    def test_validate_custom_max_age(self):
        """Test validation with custom max_age_seconds."""
        bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        old_auth_date = int(time.time()) - 7200  # 2 hours ago

        init_data = _generate_valid_init_data(
            user_id=12345,
            bot_token=bot_token,
            auth_date=old_auth_date,
        )

        # Should fail with 1-hour max age
        with pytest.raises(ValueError, match="initData is too old"):
            validate_init_data(init_data, bot_token, max_age_seconds=3600)

        # Should succeed with 3-hour max age
        user = validate_init_data(init_data, bot_token, max_age_seconds=10800)
        assert user.user_id == 12345


class TestTelegramUser:
    """Test TelegramUser dataclass."""

    def test_full_name_with_first_and_last(self):
        """Test full_name property with both names."""
        user = TelegramUser(
            user_id=12345,
            first_name="John",
            last_name="Doe",
        )
        assert user.full_name == "John Doe"

    def test_full_name_with_first_only(self):
        """Test full_name property with first name only."""
        user = TelegramUser(
            user_id=12345,
            first_name="John",
        )
        assert user.full_name == "John"

    def test_full_name_with_username_fallback(self):
        """Test full_name fallback to username."""
        user = TelegramUser(
            user_id=12345,
            username="johndoe",
        )
        assert user.full_name == "johndoe"

    def test_full_name_with_user_id_fallback(self):
        """Test full_name fallback to user_id."""
        user = TelegramUser(user_id=12345)
        assert user.full_name == "12345"
