"""Tests for chat rate limiting functionality."""
import pytest
from types import SimpleNamespace

from backend.apps.admin_ui.services import chat as chat_service
from backend.domain.candidates import services as candidate_services


class _DummyBotService:
    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok
        self.calls = []

    async def send_chat_message(self, telegram_id: int, text: str):
        self.calls.append((telegram_id, text))
        if self.ok:
            return SimpleNamespace(
                ok=True,
                status="sent",
                error=None,
                message=None,
                telegram_message_id=4242,
            )
        return SimpleNamespace(
            ok=False,
            status="failed",
            error="error",
            message=None,
            telegram_message_id=None,
        )


@pytest.mark.asyncio
async def test_rate_limit_check_allows_first_message():
    """First message should be allowed."""
    is_allowed, remaining = chat_service._check_rate_limit(999999)
    assert is_allowed is True
    assert remaining == chat_service.CHAT_RATE_LIMIT_PER_HOUR


@pytest.mark.asyncio
async def test_rate_limit_tracks_messages():
    """Messages should be recorded for rate limiting."""
    candidate_id = 888888
    # Clear any existing records
    chat_service._rate_limit_store[candidate_id] = []

    # Record some messages
    for _ in range(5):
        chat_service._record_message_sent(candidate_id)

    is_allowed, remaining = chat_service._check_rate_limit(candidate_id)
    assert is_allowed is True
    assert remaining == chat_service.CHAT_RATE_LIMIT_PER_HOUR - 5


@pytest.mark.asyncio
async def test_rate_limit_blocks_when_exceeded():
    """Messages should be blocked when limit is exceeded."""
    candidate_id = 777777
    chat_service._rate_limit_store[candidate_id] = []

    # Fill up to limit
    for _ in range(chat_service.CHAT_RATE_LIMIT_PER_HOUR):
        chat_service._record_message_sent(candidate_id)

    is_allowed, remaining = chat_service._check_rate_limit(candidate_id)
    assert is_allowed is False
    assert remaining == 0


@pytest.mark.asyncio
async def test_send_chat_message_rate_limit_error():
    """send_chat_message should return 429 when rate limit exceeded."""
    from fastapi import HTTPException

    candidate = await candidate_services.create_or_update_user(
        telegram_id=666666,
        fio="Rate Limited",
        city="Москва",
    )

    # Fill up rate limit
    chat_service._rate_limit_store[candidate.id] = []
    for _ in range(chat_service.CHAT_RATE_LIMIT_PER_HOUR):
        chat_service._record_message_sent(candidate.id)

    bot = _DummyBotService(ok=True)

    with pytest.raises(HTTPException) as exc_info:
        await chat_service.send_chat_message(
            candidate.id,
            text="Should be blocked",
            client_request_id="rate-test-1",
            author_label="admin",
            bot_service=bot,
        )

    assert exc_info.value.status_code == 429
    assert "лимит" in exc_info.value.detail["message"].lower()


@pytest.mark.asyncio
async def test_successful_send_records_for_rate_limit():
    """Successful sends should be recorded for rate limiting."""
    candidate = await candidate_services.create_or_update_user(
        telegram_id=555555,
        fio="Rate Track",
        city="Москва",
    )

    # Clear rate limit store
    chat_service._rate_limit_store[candidate.id] = []
    bot = _DummyBotService(ok=True)

    await chat_service.send_chat_message(
        candidate.id,
        text="Track this",
        client_request_id="track-1",
        author_label="admin",
        bot_service=bot,
    )

    # Check that message was recorded
    assert len(chat_service._rate_limit_store[candidate.id]) == 1


@pytest.mark.asyncio
async def test_failed_send_not_recorded_for_rate_limit():
    """Failed sends should not count against rate limit."""
    candidate = await candidate_services.create_or_update_user(
        telegram_id=444444,
        fio="No Track",
        city="Москва",
    )

    # Clear rate limit store
    chat_service._rate_limit_store[candidate.id] = []
    bot = _DummyBotService(ok=False)

    await chat_service.send_chat_message(
        candidate.id,
        text="Should fail",
        client_request_id="fail-1",
        author_label="admin",
        bot_service=bot,
    )

    # Failed message should not be recorded
    assert len(chat_service._rate_limit_store[candidate.id]) == 0
