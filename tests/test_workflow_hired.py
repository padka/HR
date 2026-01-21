"""Tests for hired/not_hired workflow actions.

These tests cover the final stage of the recruitment funnel:
- mark_hired action
- mark_not_hired action
- Status transitions and metadata updates
"""

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus


@pytest.mark.asyncio
async def test_mark_hired_from_intro_day_confirmed():
    """Test mark_hired action from INTRO_DAY_CONFIRMED_DAY_OF status."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Hired Candidate",
            city="Москва",
            candidate_status=CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
            status_changed_at=now,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        resp = await client.post(f"/api/candidates/{user_id}/actions/mark_hired")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["ok"] is True
        assert payload["status"] == CandidateStatus.HIRED.value

    # Verify DB state
    async with async_session() as session:
        stored = await session.get(User, user_id)
        assert stored.candidate_status == CandidateStatus.HIRED


@pytest.mark.asyncio
async def test_mark_not_hired_from_intro_day_confirmed():
    """Test mark_not_hired action from INTRO_DAY_CONFIRMED_DAY_OF status."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Not Hired Candidate",
            city="Москва",
            candidate_status=CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
            status_changed_at=now,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        resp = await client.post(f"/api/candidates/{user_id}/actions/mark_not_hired")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["ok"] is True
        assert payload["status"] == CandidateStatus.NOT_HIRED.value

    # Verify DB state
    async with async_session() as session:
        stored = await session.get(User, user_id)
        assert stored.candidate_status == CandidateStatus.NOT_HIRED


@pytest.mark.asyncio
async def test_mark_hired_from_preliminary_confirmed():
    """Test mark_hired action from INTRO_DAY_CONFIRMED_PRELIMINARY status."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Preliminary Hired",
            city="Москва",
            candidate_status=CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
            status_changed_at=now,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        resp = await client.post(f"/api/candidates/{user_id}/actions/mark_hired")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["ok"] is True
        assert payload["status"] == CandidateStatus.HIRED.value


@pytest.mark.asyncio
async def test_mark_hired_invalid_status_returns_error():
    """Test that mark_hired from invalid status returns error."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Invalid Status",
            city="Москва",
            candidate_status=CandidateStatus.WAITING_SLOT,
            status_changed_at=now,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        resp = await client.post(f"/api/candidates/{user_id}/actions/mark_hired")
        # Should return error because WAITING_SLOT -> HIRED is not a valid transition
        assert resp.status_code in (400, 409)


@pytest.mark.asyncio
async def test_hired_is_terminal_state():
    """Test that HIRED status has no further actions."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Terminal Hired",
            city="Москва",
            candidate_status=CandidateStatus.HIRED,
            status_changed_at=now,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        # Try to apply mark_hired again - should fail
        resp = await client.post(f"/api/candidates/{user_id}/actions/mark_hired")
        assert resp.status_code in (400, 409)

        # Try to apply mark_not_hired - should fail
        resp = await client.post(f"/api/candidates/{user_id}/actions/mark_not_hired")
        assert resp.status_code in (400, 409)


@pytest.mark.asyncio
async def test_not_hired_is_terminal_state():
    """Test that NOT_HIRED status has no further actions."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Terminal Not Hired",
            city="Москва",
            candidate_status=CandidateStatus.NOT_HIRED,
            status_changed_at=now,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        # Try to apply mark_hired - should fail
        resp = await client.post(f"/api/candidates/{user_id}/actions/mark_hired")
        assert resp.status_code in (400, 409)


@pytest.mark.asyncio
async def test_candidate_not_found_returns_404():
    """Test that non-existent candidate returns 404."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        resp = await client.post("/api/candidates/999999/actions/mark_hired")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_funnel_to_hired():
    """Test complete candidate journey from creation to hired status."""
    now = datetime.now(timezone.utc)

    # Create candidate at intro day confirmed stage (simulating completed funnel)
    async with async_session() as session:
        user = User(
            fio="Full Funnel Test",
            city="Москва",
            candidate_status=CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
            status_changed_at=now,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        # Mark as hired
        resp = await client.post(f"/api/candidates/{user_id}/actions/mark_hired")
        assert resp.status_code == 200
        assert resp.json()["status"] == CandidateStatus.HIRED.value

    # Verify final state
    async with async_session() as session:
        stored = await session.get(User, user_id)
        assert stored.candidate_status == CandidateStatus.HIRED
        assert stored.status_changed_at is not None
