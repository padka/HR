from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport

from backend.apps.admin_ui.app import create_app
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.workflow import WorkflowStatus


@pytest.mark.asyncio
async def test_workflow_state_and_actions_happy_path():
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Workflow Happy",
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
        # initial state
        resp = await client.get(f"/candidates/{user_id}/state")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == WorkflowStatus.WAITING_FOR_SLOT.value
        assert "assign-slot" in payload["allowed_actions"]

        # apply action
        resp = await client.post(f"/candidates/{user_id}/actions/assign-slot")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == WorkflowStatus.INTERVIEW_SCHEDULED.value
        assert "confirm-interview" in payload["allowed_actions"]

        # refetch
        resp = await client.get(f"/candidates/{user_id}/state")
        assert resp.status_code == 200
        assert resp.json()["status"] == WorkflowStatus.INTERVIEW_SCHEDULED.value


@pytest.mark.asyncio
async def test_workflow_reject_sets_stage_and_meta():
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Workflow Reject",
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
        resp = await client.post(f"/candidates/{user_id}/actions/reject")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == WorkflowStatus.REJECTED.value

    # verify persisted metadata
    async with async_session() as session:
        stored = await session.get(User, user_id)
        assert stored.rejection_stage == WorkflowStatus.INTERVIEW_COMPLETED.value
        assert stored.rejected_at is not None
        assert stored.rejected_by == "admin"


@pytest.mark.asyncio
async def test_workflow_invalid_transition_returns_conflict():
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        user = User(
            fio="Workflow Conflict",
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
        resp = await client.post(f"/candidates/{user_id}/actions/confirm-interview")
        assert resp.status_code == 409
        payload = resp.json()
        assert payload["detail"]["status"] == WorkflowStatus.WAITING_FOR_SLOT.value
        assert "assign-slot" in payload["detail"]["allowed_actions"]
