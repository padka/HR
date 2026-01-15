import pytest

from backend.apps.admin_ui.app import create_app
from backend.core import settings as settings_module
from backend.core.db import async_session
from backend.domain.candidates import services as candidate_services
from backend.domain.candidates.models import User, CandidateStatus


class _DummyIntegration:
    async def shutdown(self) -> None:
        return None


@pytest.fixture
def admin_app(monkeypatch):
    async def fake_setup(app):
        app.state.bot = None
        app.state.state_manager = None
        app.state.bot_service = None
        app.state.bot_integration_switch = None
        app.state.reminder_service = None
        return _DummyIntegration()

    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    settings_module.get_settings.cache_clear()
    monkeypatch.setattr("backend.apps.admin_ui.state.setup_bot_state", fake_setup)
    monkeypatch.setattr("backend.apps.admin_ui.app.setup_bot_state", fake_setup)
    app = create_app()
    try:
        yield app
    finally:
        settings_module.get_settings.cache_clear()


async def _async_get(app, path: str):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_candidate_detail_contains_chat_widget(admin_app):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=101010,
        fio="Chat Candidate",
        city="Москва",
    )

    response = await _async_get(admin_app, f"/candidates/{candidate.id}")
    assert response.status_code == 200
    assert 'data-chat-root' in response.text


@pytest.mark.asyncio
async def test_schedule_slot_button_hidden_after_test2(admin_app):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=202020,
        fio="Test2 Done",
        city="Москва",
    )
    # Save Test2 result to mark completion
    await candidate_services.save_test_result(
        user_id=candidate.id,
        raw_score=5,
        final_score=5.0,
        rating="TEST2",
        total_time=120,
        question_data=[],
    )

    response = await _async_get(admin_app, f"/candidates/{candidate.id}")
    assert response.status_code == 200
    assert "Назначить/перенести собеседование" not in response.text


@pytest.mark.asyncio
async def test_single_decline_button_for_intro_day_states(admin_app):
    candidate = await candidate_services.create_or_update_user(
        telegram_id=303030,
        fio="Intro Candidate",
        city="Москва",
    )
    # Set candidate status to intro_day_confirmed_preliminary to trigger intro-day block
    async with async_session() as session:
        db_user = await session.get(User, candidate.id)
        db_user.candidate_status = CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY
        await session.commit()

    response = await _async_get(admin_app, f"/candidates/{candidate.id}")
    assert response.status_code == 200
    # For INTRO_DAY_CONFIRMED_PRELIMINARY: should have hire/not_hired actions, but NOT decline
    assert "Закреплен на обучение" in response.text
    assert "Не закреплен" in response.text
    # Decline button only appears for INTRO_DAY_CONFIRMED_DAY_OF
    assert "decline_after_intro" not in response.text
