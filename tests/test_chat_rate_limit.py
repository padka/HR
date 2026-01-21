"""Tests for chat rate limiting functionality.

These tests use @pytest.mark.no_db_cleanup to skip database setup
and test the rate limiting logic directly without database access.
"""
import pytest
from datetime import datetime, timezone

from backend.apps.admin_ui.services import chat as chat_service


@pytest.fixture(autouse=True)
def clean_rate_limit_store():
    """Clear rate limit store before and after each test."""
    chat_service._rate_limit_store.clear()
    yield
    chat_service._rate_limit_store.clear()


@pytest.mark.no_db_cleanup
def test_rate_limit_check_allows_first_message():
    """First message should be allowed."""
    is_allowed, remaining = chat_service._check_rate_limit(999999)
    assert is_allowed is True
    assert remaining == chat_service.CHAT_RATE_LIMIT_PER_HOUR


@pytest.mark.no_db_cleanup
def test_rate_limit_tracks_messages():
    """Messages should be recorded for rate limiting."""
    candidate_id = 888888

    # Record some messages
    for _ in range(5):
        chat_service._record_message_sent(candidate_id)

    is_allowed, remaining = chat_service._check_rate_limit(candidate_id)
    assert is_allowed is True
    assert remaining == chat_service.CHAT_RATE_LIMIT_PER_HOUR - 5


@pytest.mark.no_db_cleanup
def test_rate_limit_blocks_when_exceeded():
    """Messages should be blocked when limit is exceeded."""
    candidate_id = 777777

    # Fill up to limit
    for _ in range(chat_service.CHAT_RATE_LIMIT_PER_HOUR):
        chat_service._record_message_sent(candidate_id)

    is_allowed, remaining = chat_service._check_rate_limit(candidate_id)
    assert is_allowed is False
    assert remaining == 0


@pytest.mark.no_db_cleanup
def test_rate_limit_cleans_old_entries():
    """Old entries outside the window should be cleaned."""
    candidate_id = 666666
    now = datetime.now(timezone.utc).timestamp()

    # Add old entries outside the window
    old_time = now - chat_service.CHAT_RATE_LIMIT_WINDOW_SECONDS - 100
    chat_service._rate_limit_store[candidate_id] = [old_time] * 10

    # Check should clean old entries
    is_allowed, remaining = chat_service._check_rate_limit(candidate_id)
    assert is_allowed is True
    assert remaining == chat_service.CHAT_RATE_LIMIT_PER_HOUR
    assert len(chat_service._rate_limit_store[candidate_id]) == 0


@pytest.mark.no_db_cleanup
def test_rate_limit_record_adds_timestamp():
    """Recording a message should add current timestamp."""
    candidate_id = 555555

    before = datetime.now(timezone.utc).timestamp()
    chat_service._record_message_sent(candidate_id)
    after = datetime.now(timezone.utc).timestamp()

    assert len(chat_service._rate_limit_store[candidate_id]) == 1
    recorded_ts = chat_service._rate_limit_store[candidate_id][0]
    assert before <= recorded_ts <= after


@pytest.mark.no_db_cleanup
def test_rate_limit_config_values():
    """Verify rate limit configuration values are sensible."""
    assert chat_service.CHAT_RATE_LIMIT_PER_HOUR == 20
    assert chat_service.CHAT_RATE_LIMIT_WINDOW_SECONDS == 3600  # 1 hour


@pytest.mark.no_db_cleanup
def test_multiple_candidates_independent():
    """Rate limits should be tracked independently per candidate."""
    candidate_a = 111111
    candidate_b = 222222

    # Max out candidate A
    for _ in range(chat_service.CHAT_RATE_LIMIT_PER_HOUR):
        chat_service._record_message_sent(candidate_a)

    # Candidate A should be blocked
    is_allowed_a, _ = chat_service._check_rate_limit(candidate_a)
    assert is_allowed_a is False

    # Candidate B should still be allowed
    is_allowed_b, remaining_b = chat_service._check_rate_limit(candidate_b)
    assert is_allowed_b is True
    assert remaining_b == chat_service.CHAT_RATE_LIMIT_PER_HOUR
