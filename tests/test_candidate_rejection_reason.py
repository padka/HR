import pytest
from backend.apps.admin_ui.services.candidates import update_candidate_status
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.core.db import async_session
from sqlalchemy import select

@pytest.mark.asyncio
async def test_update_candidate_status_with_reason():
    # 1. Create a test candidate
    async with async_session() as session:
        user = User(fio="Test Reason Candidate", telegram_id=999999999, candidate_status=CandidateStatus.TEST1_COMPLETED)
        session.add(user)
        await session.commit()
        candidate_id = user.id

    # 2. Update status with reason
    reason_text = "Does not meet criteria"
    ok, message, status, _ = await update_candidate_status(
        candidate_id, 
        "interview_declined", 
        reason=reason_text
    )
    
    assert ok is True
    
    # 3. Verify in DB
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == candidate_id))
        updated_user = result.scalar_one()
        assert updated_user.candidate_status == CandidateStatus.INTERVIEW_DECLINED
        assert updated_user.rejection_reason == reason_text

    # Cleanup
    async with async_session() as session:
        await session.delete(updated_user)
        await session.commit()
