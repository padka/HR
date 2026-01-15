from itertools import count

import pytest
from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus, can_transition, is_status_retreat
from backend.domain.candidates.status_service import (
    StatusTransitionError,
    set_status_hired,
    set_status_interview_confirmed,
    set_status_interview_scheduled,
    set_status_test2_completed,
    set_status_test2_sent,
    update_candidate_status,
)

_tg_counter = count(1_000_000)


async def _create_user(status: CandidateStatus) -> int:
    tg_id = next(_tg_counter)
    async with async_session() as session:
        user = User(
            telegram_id=tg_id,
            fio=f"Test User {tg_id}",
            city="Test City",
            is_active=True,
            candidate_status=status,
        )
        session.add(user)
        await session.commit()
    return tg_id


@pytest.mark.asyncio
async def test_invalid_jump_requires_force():
    tg_id = await _create_user(CandidateStatus.TEST1_COMPLETED)
    with pytest.raises(StatusTransitionError):
        await update_candidate_status(tg_id, CandidateStatus.HIRED)


@pytest.mark.asyncio
async def test_force_allows_jump_to_hired():
    tg_id = await _create_user(CandidateStatus.TEST1_COMPLETED)
    assert await set_status_hired(tg_id, force=True)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one()
    assert user.candidate_status == CandidateStatus.HIRED


@pytest.mark.asyncio
async def test_forward_pipeline_allows_test2_completion():
    tg_id = await _create_user(CandidateStatus.TEST1_COMPLETED)
    assert await set_status_interview_scheduled(tg_id)
    assert await set_status_interview_confirmed(tg_id)
    assert await set_status_test2_sent(tg_id)
    assert await set_status_test2_completed(tg_id)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one()
    assert user.candidate_status == CandidateStatus.TEST2_COMPLETED


@pytest.mark.asyncio
async def test_idempotent_update_returns_true_and_keeps_status():
    tg_id = await _create_user(CandidateStatus.INTERVIEW_CONFIRMED)
    assert await update_candidate_status(tg_id, CandidateStatus.INTERVIEW_CONFIRMED)
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg_id))
    assert user.candidate_status == CandidateStatus.INTERVIEW_CONFIRMED


@pytest.mark.asyncio
async def test_retreating_status_is_ignored_but_not_error():
    tg_id = await _create_user(CandidateStatus.TEST2_COMPLETED)
    # Retreat to earlier stage should be ignored
    assert await update_candidate_status(tg_id, CandidateStatus.INTERVIEW_CONFIRMED)
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg_id))
    assert user.candidate_status == CandidateStatus.TEST2_COMPLETED


@pytest.mark.asyncio
async def test_matrix_matches_status_transition_rules():
    for current in CandidateStatus:
        for target in CandidateStatus:
            tg_id = await _create_user(current)
            if target == current:
                assert await update_candidate_status(tg_id, target)
                expected = current
            elif is_status_retreat(current, target):
                assert await update_candidate_status(tg_id, target)
                expected = current  # retreat is a no-op
            elif can_transition(current, target):
                assert await update_candidate_status(tg_id, target)
                expected = target
            else:
                with pytest.raises(StatusTransitionError):
                    await update_candidate_status(tg_id, target)
                expected = current

            async with async_session() as session:
                user = await session.scalar(select(User).where(User.telegram_id == tg_id))
            assert user.candidate_status == expected
