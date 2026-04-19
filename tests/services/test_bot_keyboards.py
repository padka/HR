from datetime import datetime, timedelta, timezone
import sys
import types

import pytest

# Provide a tiny aiogram.types stub when the real dependency isn't installed.
try:  # pragma: no cover - best effort import
    import aiogram as _aiogram  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - fallback stub
    fake_aiogram = types.ModuleType("aiogram")
    fake_types = types.ModuleType("aiogram.types")
    fake_client = types.ModuleType("aiogram.client")
    fake_client_bot = types.ModuleType("aiogram.client.bot")
    fake_enums = types.ModuleType("aiogram.enums")

    class _FakeWebAppInfo:
        def __init__(self, *, url: str = ""):
            self.url = url

    class _FakeInlineKeyboardButton:
        def __init__(self, *, text: str, callback_data: str = "", url: str = "", web_app: object = None):
            self.text = text
            self.callback_data = callback_data
            self.url = url
            self.web_app = web_app

    class _FakeInlineKeyboardMarkup:
        def __init__(self, *, inline_keyboard):
            self.inline_keyboard = inline_keyboard

    class _FakeDefaultBotProperties:
        def __init__(self, **_: object):
            pass

    class _FakeParseMode:
        HTML = "HTML"

    fake_types.WebAppInfo = _FakeWebAppInfo
    fake_types.InlineKeyboardButton = _FakeInlineKeyboardButton
    fake_types.InlineKeyboardMarkup = _FakeInlineKeyboardMarkup
    fake_client_bot.DefaultBotProperties = _FakeDefaultBotProperties
    fake_enums.ParseMode = _FakeParseMode
    fake_aiogram.types = fake_types
    fake_aiogram.client = fake_client
    fake_client.bot = fake_client_bot

    sys.modules["aiogram"] = fake_aiogram
    sys.modules["aiogram.types"] = fake_types
    sys.modules["aiogram.client"] = fake_client
    sys.modules["aiogram.client.bot"] = fake_client_bot
    sys.modules["aiogram.enums"] = fake_enums

from backend.apps.bot import keyboards
from backend.apps.bot.keyboards import (
    kb_approve,
    kb_candidate_actions,
    kb_candidate_notification,
    kb_recruiter_dashboard,
    kb_recruiters,
    kb_slot_assignment_active,
    kb_slot_assignment_reschedule_options,
)
from backend.apps.bot.config import DEFAULT_TZ
from backend.core.db import async_session
from backend.domain import models


@pytest.mark.asyncio
async def test_kb_recruiters_handles_duplicate_names_with_slots():
    async with async_session() as session:
        _first = models.Recruiter(name="Анна", tz="Europe/Moscow", active=True)
        second = models.Recruiter(name="Анна", tz="Europe/Moscow", active=True)
        session.add_all([_first, second])
        await session.flush()

        target_id = second.id
        session.add(
            models.Slot(
                recruiter_id=target_id,
                start_utc=datetime.now(timezone.utc) + timedelta(hours=2),
                status=models.SlotStatus.FREE,
            )
        )
        await session.commit()

    keyboard = await kb_recruiters()

    buttons = [
        btn
        for row in keyboard.inline_keyboard
        for btn in row
        if getattr(btn, "callback_data", "").startswith("pick_rec:")
    ]

    assert buttons, "expected recruiter buttons to be present"
    assert any(btn.callback_data.endswith(str(target_id)) for btn in buttons)
    assert all("Временно нет свободных рекрутёров" not in btn.text for btn in buttons)


@pytest.mark.asyncio
async def test_kb_recruiters_uses_aggregated_repository(monkeypatch):
    class _Obj:
        def __init__(self, rid: int, name: str):
            self.id = rid
            self.name = name

    active_calls = 0

    async def fake_get_active_recruiters():
        nonlocal active_calls
        active_calls += 1
        return [_Obj(1, "Анна"), _Obj(2, "Борис")]

    summary_calls = 0

    async def fake_summary(recruiter_ids, now_utc=None, *, city_id=None):
        nonlocal summary_calls
        summary_calls += 1
        assert set(recruiter_ids) == {1, 2}
        return {1: (datetime.now(timezone.utc), 4)}

    monkeypatch.setattr(keyboards, "get_active_recruiters", fake_get_active_recruiters)
    monkeypatch.setattr(keyboards, "get_recruiters_free_slots_summary", fake_summary)

    keyboard = await keyboards.kb_recruiters()

    assert summary_calls == 1
    assert active_calls == 1
    assert keyboard.inline_keyboard


@pytest.mark.asyncio
async def test_kb_recruiters_handles_uppercase_status():
    async with async_session() as session:
        recruiter = models.Recruiter(name="Борис", tz="Europe/Moscow", active=True)
        session.add(recruiter)
        await session.flush()

        await session.execute(
            models.Slot.__table__.insert().values(
                recruiter_id=recruiter.id,
                start_utc=datetime.now(timezone.utc) + timedelta(hours=1),
                duration_min=60,
                status="FREE",
            )
        )
        await session.commit()

    keyboard = await kb_recruiters()

    buttons = [
        btn
        for row in keyboard.inline_keyboard
        for btn in row
        if getattr(btn, "callback_data", "").startswith("pick_rec:")
    ]

    assert buttons, "expected recruiter buttons to be present"
    assert any(btn.callback_data.endswith(str(recruiter.id)) for btn in buttons)


@pytest.mark.asyncio
async def test_kb_recruiters_filters_by_city():
    async with async_session() as session:
        rec1 = models.Recruiter(name="Городской", tz="Europe/Moscow", active=True)
        rec2 = models.Recruiter(name="Дальний", tz="Europe/Samara", active=True)
        city1 = models.City(name="Москва", tz="Europe/Moscow", active=True)
        city2 = models.City(name="Самара", tz="Europe/Samara", active=True)
        rec1.cities.append(city1)
        rec2.cities.append(city2)
        session.add_all([rec1, rec2, city1, city2])
        await session.commit()
        await session.refresh(rec1)
        await session.refresh(rec2)
        await session.refresh(city1)
        await session.refresh(city2)

        now = datetime.now(timezone.utc)
        session.add_all(
            [
                models.Slot(
                    recruiter_id=rec1.id,
                    city_id=city1.id,
                    start_utc=now + timedelta(hours=1),
                    status=models.SlotStatus.FREE,
                ),
                models.Slot(
                    recruiter_id=rec2.id,
                    city_id=city2.id,
                    start_utc=now + timedelta(hours=1),
                    status=models.SlotStatus.FREE,
                ),
            ]
        )
        await session.commit()

    keyboard = await kb_recruiters(candidate_tz=DEFAULT_TZ, city_id=city1.id)
    buttons = [
        btn
        for row in keyboard.inline_keyboard
        for btn in row
        if getattr(btn, "callback_data", "").startswith("pick_rec:")
    ]

    assert buttons
    assert any(btn.callback_data.endswith(str(rec1.id)) for btn in buttons)
    assert all(not btn.callback_data.endswith(str(rec2.id)) for btn in buttons)


@pytest.mark.asyncio
async def test_kb_recruiters_no_slots_has_contact_button():
    async with async_session() as session:
        city = models.City(name="Без слотов", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)

    keyboard = await kb_recruiters(candidate_tz=DEFAULT_TZ, city_id=city.id)

    contact_buttons = [
        btn
        for row in keyboard.inline_keyboard
        for btn in row
        if getattr(btn, "callback_data", "") == "contact:manual"
    ]

    assert contact_buttons, "expected contact button when no recruiters are available"


# ---------------------------------------------------------------------------
# Tests for new recruiter keyboard builders (Phase 1)
# ---------------------------------------------------------------------------


def _all_buttons(kb):
    """Flatten inline keyboard into a list of buttons."""
    return [btn for row in kb.inline_keyboard for btn in row]


def _buttons_with_text(kb, text_substr):
    return [btn for btn in _all_buttons(kb) if text_substr in btn.text]


def test_kb_approve_without_crm_url():
    kb = kb_approve(42)
    buttons = _all_buttons(kb)
    assert any("Согласовано" in btn.text for btn in buttons)
    assert not any(getattr(btn, "url", None) for btn in buttons), "no URL buttons expected"


def test_kb_approve_with_crm_url():
    kb = kb_approve(42, crm_url="https://example.com/app/candidates/7")
    buttons = _all_buttons(kb)
    url_buttons = [btn for btn in buttons if getattr(btn, "url", None)]
    assert url_buttons, "expected a CRM URL button"
    assert url_buttons[0].url == "https://example.com/app/candidates/7"
    assert "CRM" in url_buttons[0].text


def test_kb_candidate_notification_has_action_buttons():
    kb = kb_candidate_notification(99, "https://crm.test/app/candidates/99")
    buttons = _all_buttons(kb)
    texts = [btn.text for btn in buttons]
    assert any("Статус" in t for t in texts)
    assert any("Написать" in t for t in texts)
    url_buttons = [btn for btn in buttons if getattr(btn, "url", None)]
    assert url_buttons
    assert "candidates/99" in url_buttons[0].url


def test_kb_candidate_notification_no_crm_url():
    kb = kb_candidate_notification(99, "")
    url_buttons = [btn for btn in _all_buttons(kb) if getattr(btn, "url", None)]
    assert not url_buttons, "no URL button when crm_url is empty"


def test_kb_candidate_actions_has_action_buttons():
    kb = kb_candidate_actions(55, "https://crm.test/app/candidates/55")
    buttons = _all_buttons(kb)
    texts = [btn.text for btn in buttons]
    assert any("Статус" in t for t in texts)
    assert any("Написать" in t for t in texts)
    url_buttons = [btn for btn in buttons if getattr(btn, "url", None)]
    assert url_buttons
    assert "candidates/55" in url_buttons[0].url


def test_kb_recruiter_dashboard_with_waiting():
    kb = kb_recruiter_dashboard(3, "https://crm.test")
    buttons = _all_buttons(kb)
    inbox_btns = _buttons_with_text(kb, "Входящие")
    assert inbox_btns
    assert "(3)" in inbox_btns[0].text
    url_buttons = [btn for btn in buttons if getattr(btn, "url", None)]
    assert url_buttons
    assert "dashboard" in url_buttons[0].url


def test_kb_recruiter_dashboard_no_waiting():
    kb = kb_recruiter_dashboard(0, "https://crm.test")
    inbox_btns = _buttons_with_text(kb, "Входящие")
    assert inbox_btns
    assert "(0)" not in inbox_btns[0].text


def test_kb_recruiter_dashboard_no_crm_url():
    kb = kb_recruiter_dashboard(2, "")
    url_buttons = [btn for btn in _all_buttons(kb) if getattr(btn, "url", None)]
    assert not url_buttons, "no URL button when crm_url is empty"


def test_kb_slot_assignment_reschedule_options_has_manual_fallback():
    slots = [
        types.SimpleNamespace(
            id=101,
            start_utc=datetime(2031, 7, 1, 10, 0, tzinfo=timezone.utc),
            duration_min=30,
        ),
        types.SimpleNamespace(
            id=102,
            start_utc=datetime(2031, 7, 1, 11, 0, tzinfo=timezone.utc),
            duration_min=30,
        ),
    ]

    kb = kb_slot_assignment_reschedule_options(
        55,
        candidate_tz=DEFAULT_TZ,
        slots=slots,
    )
    callbacks = [getattr(btn, "callback_data", "") for btn in _all_buttons(kb)]

    assert any(value.startswith("slotres:pick:55:101") for value in callbacks)
    assert any(value.startswith("slotres:manual:55") for value in callbacks)


def test_kb_slot_assignment_active_has_details_and_controls():
    kb = kb_slot_assignment_active(
        55,
        reschedule_token="reschedule-token",
        decline_token="decline-token",
    )
    buttons = _all_buttons(kb)
    texts = [btn.text for btn in buttons]
    callbacks = [getattr(btn, "callback_data", "") for btn in buttons]

    assert "🗓 Детали встречи" in texts
    assert "🔁 Перенести" in texts
    assert "⛔️ Отменить" in texts
    assert any(value.startswith("slotasg:details:55") for value in callbacks)
    assert any('"a":"reschedule"' in value for value in callbacks)
    assert any('"a":"decline"' in value for value in callbacks)


# ---------------------------------------------------------------------------
# Tests for WebAppInfo (Mini App) buttons
# ---------------------------------------------------------------------------


def _webapp_buttons(kb):
    """Get all buttons that have a web_app attribute set."""
    return [btn for btn in _all_buttons(kb) if getattr(btn, "web_app", None)]


def test_kb_candidate_notification_has_webapp_button():
    kb = kb_candidate_notification(99, "https://crm.test/app/candidates/99")
    wa_btns = _webapp_buttons(kb)
    assert wa_btns, "expected a WebApp profile button"
    assert "tg-app/candidates/99" in wa_btns[0].web_app.url
    assert "Профиль" in wa_btns[0].text


def test_kb_candidate_notification_no_webapp_without_crm():
    kb = kb_candidate_notification(99, "")
    wa_btns = _webapp_buttons(kb)
    assert not wa_btns, "no WebApp button when crm_url is empty"


def test_kb_candidate_actions_has_webapp_button():
    kb = kb_candidate_actions(55, "https://crm.test/app/candidates/55")
    wa_btns = _webapp_buttons(kb)
    assert wa_btns, "expected a WebApp profile button"
    assert "tg-app/candidates/55" in wa_btns[0].web_app.url


def test_kb_recruiter_dashboard_has_webapp_button():
    kb = kb_recruiter_dashboard(3, "https://crm.test")
    wa_btns = _webapp_buttons(kb)
    assert wa_btns, "expected a WebApp button on dashboard"
    assert "tg-app/incoming" in wa_btns[0].web_app.url
    assert "Приложение" in wa_btns[0].text


def test_kb_recruiter_dashboard_no_webapp_without_crm():
    kb = kb_recruiter_dashboard(3, "")
    wa_btns = _webapp_buttons(kb)
    assert not wa_btns, "no WebApp button when crm_url is empty"
