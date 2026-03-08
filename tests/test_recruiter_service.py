"""Tests for recruiter_service.py — Phase 2 flows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.apps.bot.recruiter_service import (
    _CODE_TO_STATUS,
    _STATUS_TO_CODE,
    _crm_base_url,
    _crm_candidate_url,
    handle_recruiter_free_text,
    search_candidates,
    set_recruiter_commands,
)
from backend.domain.candidates.status import CandidateStatus


# ---------------------------------------------------------------------------
# Status code mapping tests
# ---------------------------------------------------------------------------


def test_status_code_roundtrip():
    """Every CandidateStatus value has a code and codes round-trip back."""
    for status in CandidateStatus:
        code = _STATUS_TO_CODE.get(status.value)
        assert code is not None, f"Missing code for {status.value}"
        assert _CODE_TO_STATUS[code] == status.value


def test_status_codes_are_short():
    """All status codes fit within the callback data budget."""
    for code in _STATUS_TO_CODE.values():
        # Max 3 chars for status code
        assert len(code) <= 3, f"Code too long: {code}"


def test_no_duplicate_codes():
    """Each code maps to exactly one status."""
    codes = list(_STATUS_TO_CODE.values())
    assert len(codes) == len(set(codes)), "Duplicate status codes found"


# ---------------------------------------------------------------------------
# CRM URL helpers
# ---------------------------------------------------------------------------


def test_crm_candidate_url_with_base(monkeypatch):
    """CRM candidate URL is built correctly when base URL is set."""
    from backend.apps.bot import recruiter_service as _rs

    monkeypatch.setattr(_rs, "_crm_base_url", lambda: "https://crm.example.com")
    url = _crm_candidate_url(42)
    assert url == "https://crm.example.com/app/candidates/42"


def test_crm_candidate_url_without_base(monkeypatch):
    """CRM candidate URL is empty when base URL is not set."""
    from backend.apps.bot import recruiter_service as _rs

    monkeypatch.setattr(_rs, "_crm_base_url", lambda: "")
    url = _crm_candidate_url(42)
    assert url == ""


def test_crm_base_url_prefers_public_url(monkeypatch):
    """Public CRM URL should win over internal backend URL for recruiter links."""
    from backend.apps.bot import recruiter_service as _rs

    monkeypatch.setattr(
        _rs,
        "get_settings",
        lambda: SimpleNamespace(
            crm_public_url="https://crm.example.com",
            bot_backend_url="http://127.0.0.1:8010",
        ),
    )
    assert _crm_base_url() == "https://crm.example.com"


def test_crm_base_url_falls_back_to_bot_backend_url(monkeypatch):
    """Internal backend URL remains the fallback when no public CRM URL is configured."""
    from backend.apps.bot import recruiter_service as _rs

    monkeypatch.setattr(
        _rs,
        "get_settings",
        lambda: SimpleNamespace(
            crm_public_url="",
            bot_backend_url="http://127.0.0.1:8010",
        ),
    )
    assert _crm_base_url() == "http://127.0.0.1:8010"


# ---------------------------------------------------------------------------
# Free-text messaging state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_recruiter_free_text_no_state(monkeypatch):
    """Returns False when recruiter has no pending message state."""
    from backend.apps.bot import recruiter_service

    class FakeStateManager:
        async def get(self, key):
            return None

        async def set(self, key, value):
            pass

        async def delete(self, key):
            pass

    monkeypatch.setattr(recruiter_service, "get_state_manager", lambda: FakeStateManager())
    result = await handle_recruiter_free_text(12345, "hello")
    assert result is False


@pytest.mark.asyncio
async def test_handle_recruiter_free_text_with_state(monkeypatch):
    """Returns True, persists outbound chat, and confirms to the recruiter."""
    from backend.apps.bot import recruiter_service

    forwarded_messages = []
    sent_messages = []

    class FakeBot:
        async def send_message(self, chat_id, text, **kwargs):
            sent_messages.append({"chat_id": chat_id, "text": text})

    state_store = {}

    class FakeStateManager:
        async def get(self, key):
            return state_store.get(key)

        async def set(self, key, value):
            state_store[key] = value

        async def delete(self, key):
            state_store.pop(key, None)

    # Set up state
    rc_state = {
        "rc_awaiting_msg": True,
        "rc_target_id": 7,
        "rc_target_tg_id": 99999,
        "rc_target_name": "Иван",
    }
    state_store["rc:12345"] = rc_state

    async def fake_send_chat_message(candidate_id, *, text, client_request_id, author_label, bot_service, reply_markup=None):
        forwarded_messages.append(
            {
                "candidate_id": candidate_id,
                "text": text,
                "client_request_id": client_request_id,
                "author_label": author_label,
            }
        )
        return {"status": "sent", "message": {"status": "sent"}}

    monkeypatch.setattr(recruiter_service, "get_state_manager", lambda: FakeStateManager())
    monkeypatch.setattr(recruiter_service, "get_bot", lambda: FakeBot())
    monkeypatch.setattr(recruiter_service, "get_bot_service", lambda: object())
    monkeypatch.setattr(recruiter_service, "send_chat_message", fake_send_chat_message)

    result = await handle_recruiter_free_text(12345, "Привет, приходите завтра!")
    assert result is True

    assert forwarded_messages == [
        {
            "candidate_id": 7,
            "text": "Привет, приходите завтра!",
            "client_request_id": None,
            "author_label": "Рекрутер",
        }
    ]
    assert sent_messages == [
        {
            "chat_id": 12345,
            "text": "✅ Сообщение отправлено для <b>Иван</b>.",
        }
    ]

    # State should be cleared
    assert "rc:12345" not in state_store
