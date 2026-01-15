"""Tests for the new /api/candidates/{id}/actions/{action} endpoint."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.workflow import WorkflowStatus


@pytest.mark.asyncio
async def test_action_reject_updates_workflow_status():
    """POST /api/candidates/{id}/actions/reject should reject candidate."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Action Reject Test",
            city="Москва",
            workflow_status=WorkflowStatus.INTERVIEW_COMPLETED.value,
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
        resp = await client.post(f"/api/candidates/{user_id}/actions/reject")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == WorkflowStatus.REJECTED.value

    # verify persisted
    async with async_session() as session:
        stored = await session.get(User, user_id)
        assert stored.workflow_status == WorkflowStatus.REJECTED.value
        assert stored.rejection_stage == WorkflowStatus.INTERVIEW_COMPLETED.value


@pytest.mark.asyncio
async def test_action_mark_hired():
    """POST /api/candidates/{id}/actions/mark_hired should update status."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Action Hired Test",
            city="Москва",
            workflow_status=WorkflowStatus.INTRO_DAY_COMPLETED.value,
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
        resp = await client.post(f"/api/candidates/{user_id}/actions/mark-hired")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == WorkflowStatus.HIRED.value


@pytest.mark.asyncio
async def test_action_mark_not_hired():
    """POST /api/candidates/{id}/actions/mark_not_hired should update status."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Action Not Hired Test",
            city="Москва",
            workflow_status=WorkflowStatus.INTRO_DAY_COMPLETED.value,
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
        resp = await client.post(f"/api/candidates/{user_id}/actions/mark-not-hired")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == WorkflowStatus.NOT_HIRED.value


@pytest.mark.asyncio
async def test_action_invalid_returns_404():
    """Invalid action should return 404."""
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Action Invalid Test",
            city="Москва",
            workflow_status=WorkflowStatus.WAITING_FOR_SLOT.value,
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
        resp = await client.post(f"/api/candidates/{user_id}/actions/nonexistent-action")
        assert resp.status_code in (404, 409)  # 404 for unknown action or 409 for invalid transition


@pytest.mark.asyncio
async def test_action_candidate_not_found():
    """Action on non-existent candidate should return 404."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        auth=("admin", "admin"),
    ) as client:
        resp = await client.post("/api/candidates/999999999/actions/reject")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_actions_url_patterns_work():
    """Verify that URL patterns from actions.py work correctly."""
    from backend.domain.candidates.actions import STATUS_ACTIONS, CandidateAction

    # Check that all POST actions have proper API URL patterns
    for status, actions in STATUS_ACTIONS.items():
        for action in actions:
            if action.method == "POST":
                assert "/api/candidates/{id}/actions/" in action.url_pattern, \
                    f"POST action {action.key} should use new API pattern, got {action.url_pattern}"
