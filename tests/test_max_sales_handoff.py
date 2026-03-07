from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional

import pytest

import backend.apps.admin_ui.services.max_sales_handoff as handoff
import backend.core.messenger.registry as registry_mod
from backend.core.messenger.protocol import MessengerPlatform, MessengerProtocol, SendResult
from backend.core.messenger.registry import MessengerRegistry


class _FakeMaxAdapter(MessengerProtocol):
    platform = MessengerPlatform.MAX

    def __init__(self, *, fail_targets: Optional[set[str]] = None) -> None:
        self.fail_targets = fail_targets or set()
        self.calls: list[dict[str, Any]] = []

    async def configure(self, **kwargs: Any) -> None:
        return None

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        buttons=None,
        parse_mode=None,
        correlation_id=None,
    ) -> SendResult:
        chat_key = str(chat_id)
        self.calls.append(
            {
                "chat_id": chat_key,
                "text": text,
                "parse_mode": parse_mode,
                "correlation_id": correlation_id,
            }
        )
        if chat_key in self.fail_targets:
            return SendResult(success=False, error="target_unavailable")
        return SendResult(success=True, message_id=f"mid_{chat_key}")


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    reg = MessengerRegistry()
    monkeypatch.setattr(registry_mod, "_registry", reg)
    return reg


def _context(**overrides: Any) -> handoff.IntroDayHandoffContext:
    payload: dict[str, Any] = {
        "candidate_id": 101,
        "candidate_fio": "Иван Иванов",
        "slot_id": 555,
        "slot_start_utc": datetime(2030, 1, 20, 9, 0, tzinfo=timezone.utc),
        "slot_tz": "Europe/Moscow",
        "recruiter_id": 7,
        "recruiter_name": "Рекрутер",
        "city_id": 10,
        "city_name": "Москва",
        "candidate_card_url": "https://example.com/app/candidates/101",
        "hh_profile_url": "https://hh.ru/resume/abc123",
    }
    payload.update(overrides)
    return handoff.IntroDayHandoffContext(**payload)


@pytest.mark.asyncio
async def test_handoff_skips_when_feature_disabled(monkeypatch) -> None:
    monkeypatch.delenv(handoff.MAX_INTRO_DAY_HANDOFF_ENABLED_ENV, raising=False)
    monkeypatch.setattr(
        handoff,
        "get_settings",
        lambda: SimpleNamespace(max_bot_enabled=True, max_bot_token="token"),
    )

    result = await handoff.dispatch_intro_day_handoff_to_max(_context())

    assert result["ok"] is False
    assert result["status"] == "skipped:feature_disabled"


@pytest.mark.asyncio
async def test_handoff_prefers_recruiter_route(monkeypatch, _isolated_registry) -> None:
    monkeypatch.setenv(handoff.MAX_INTRO_DAY_HANDOFF_ENABLED_ENV, "true")
    monkeypatch.setenv(
        handoff.MAX_INTRO_DAY_GROUP_ROUTES_ENV,
        json.dumps(
            {
                "default": ["group_default"],
                "cities": {"10": ["group_city"]},
                "recruiters": {"7": ["group_recruiter"]},
            }
        ),
    )
    monkeypatch.setattr(
        handoff,
        "get_settings",
        lambda: SimpleNamespace(max_bot_enabled=True, max_bot_token="token"),
    )

    adapter = _FakeMaxAdapter()
    _isolated_registry.register(adapter)

    result = await handoff.dispatch_intro_day_handoff_to_max(_context())

    assert result["status"] == "sent"
    assert result["route"] == "recruiter:7"
    assert result["targets_sent"] == 1
    assert adapter.calls[0]["chat_id"] == "group_recruiter"
    assert "Резюме:" in adapter.calls[0]["text"]


@pytest.mark.asyncio
async def test_handoff_uses_city_name_route(monkeypatch, _isolated_registry) -> None:
    monkeypatch.setenv(handoff.MAX_INTRO_DAY_HANDOFF_ENABLED_ENV, "1")
    monkeypatch.setenv(
        handoff.MAX_INTRO_DAY_GROUP_ROUTES_ENV,
        json.dumps(
            {
                "city_names": {"москва": ["group_city_name"]},
            }
        ),
    )
    monkeypatch.setattr(
        handoff,
        "get_settings",
        lambda: SimpleNamespace(max_bot_enabled=True, max_bot_token="token"),
    )

    adapter = _FakeMaxAdapter()
    _isolated_registry.register(adapter)

    result = await handoff.dispatch_intro_day_handoff_to_max(
        _context(city_id=None, recruiter_id=None)
    )

    assert result["status"] == "sent"
    assert result["route"] == "city_name:москва"
    assert adapter.calls[0]["chat_id"] == "group_city_name"


@pytest.mark.asyncio
async def test_handoff_reports_partial_failures(monkeypatch, _isolated_registry) -> None:
    monkeypatch.setenv(handoff.MAX_INTRO_DAY_HANDOFF_ENABLED_ENV, "true")
    monkeypatch.setenv(
        handoff.MAX_INTRO_DAY_GROUP_ROUTES_ENV,
        json.dumps(
            {
                "default": ["group_one", "group_two"],
            }
        ),
    )
    monkeypatch.setattr(
        handoff,
        "get_settings",
        lambda: SimpleNamespace(max_bot_enabled=True, max_bot_token="token"),
    )

    adapter = _FakeMaxAdapter(fail_targets={"group_two"})
    _isolated_registry.register(adapter)

    result = await handoff.dispatch_intro_day_handoff_to_max(
        _context(recruiter_id=None, city_id=None, city_name=None)
    )

    assert result["status"] == "partial"
    assert result["targets_total"] == 2
    assert result["targets_sent"] == 1
    assert result["targets_failed"] == 1
    assert any("group_two" in item for item in result.get("errors", []))

