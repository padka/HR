"""Tests for hh.ru sync integration: mapping, resolver, dispatcher."""

from itertools import count
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.hh_sync.mapping import (
    HH_STATUS_MAPPING,
    get_hh_target_status,
    should_sync_status,
)
from backend.domain.hh_sync.resolver import parse_resume_id
from backend.domain.hh_sync.models import HHSyncLog
from backend.domain.models import OutboxNotification

_tg_counter = count(2_000_000)


# ---------------------------------------------------------------------------
# Mapping tests
# ---------------------------------------------------------------------------


class TestHHStatusMapping:
    def test_interview_scheduled_maps_to_invitation(self):
        assert get_hh_target_status(CandidateStatus.INTERVIEW_SCHEDULED) == "invitation"

    def test_interview_confirmed_maps_to_invitation(self):
        assert get_hh_target_status(CandidateStatus.INTERVIEW_CONFIRMED) == "invitation"

    def test_interview_declined_maps_to_discard(self):
        assert get_hh_target_status(CandidateStatus.INTERVIEW_DECLINED) == "discard"

    def test_test2_failed_maps_to_discard(self):
        assert get_hh_target_status(CandidateStatus.TEST2_FAILED) == "discard"

    def test_intro_day_declined_invitation_maps_to_discard(self):
        assert get_hh_target_status(CandidateStatus.INTRO_DAY_DECLINED_INVITATION) == "discard"

    def test_intro_day_declined_day_of_maps_to_discard(self):
        assert get_hh_target_status(CandidateStatus.INTRO_DAY_DECLINED_DAY_OF) == "discard"

    def test_not_hired_maps_to_discard(self):
        assert get_hh_target_status(CandidateStatus.NOT_HIRED) == "discard"

    def test_hired_maps_to_hired(self):
        assert get_hh_target_status(CandidateStatus.HIRED) == "hired"

    def test_internal_statuses_return_none(self):
        """Internal statuses should not trigger hh.ru sync."""
        internal_statuses = [
            CandidateStatus.LEAD,
            CandidateStatus.CONTACTED,
            CandidateStatus.INVITED,
            CandidateStatus.TEST1_COMPLETED,
            CandidateStatus.WAITING_SLOT,
            CandidateStatus.STALLED_WAITING_SLOT,
            CandidateStatus.SLOT_PENDING,
            CandidateStatus.TEST2_SENT,
            CandidateStatus.TEST2_COMPLETED,
            CandidateStatus.INTRO_DAY_SCHEDULED,
            CandidateStatus.INTRO_DAY_CONFIRMED_PRELIMINARY,
            CandidateStatus.INTRO_DAY_CONFIRMED_DAY_OF,
        ]
        for status in internal_statuses:
            assert get_hh_target_status(status) is None, f"{status} should not map to hh.ru"

    def test_should_sync_status_positive(self):
        for status in HH_STATUS_MAPPING:
            assert should_sync_status(status) is True

    def test_should_sync_status_negative(self):
        assert should_sync_status(CandidateStatus.TEST1_COMPLETED) is False


# ---------------------------------------------------------------------------
# Resolver / URL parser tests
# ---------------------------------------------------------------------------


class TestResumeURLParser:
    def test_standard_url(self):
        assert parse_resume_id("https://hh.ru/resume/abc123def") == "abc123def"

    def test_url_with_subdomain(self):
        assert parse_resume_id("https://spb.hh.ru/resume/xyz789") == "xyz789"

    def test_url_with_query_params(self):
        assert parse_resume_id("https://hh.ru/resume/abc123?from=search&foo=bar") == "abc123"

    def test_http_url(self):
        assert parse_resume_id("http://hh.ru/resume/test456") == "test456"

    def test_invalid_url_returns_none(self):
        assert parse_resume_id("https://example.com/resume/abc") is None

    def test_empty_string_returns_none(self):
        assert parse_resume_id("") is None

    def test_none_returns_none(self):
        assert parse_resume_id(None) is None

    def test_url_with_whitespace(self):
        assert parse_resume_id("  https://hh.ru/resume/abc123  ") == "abc123"

    def test_not_resume_url(self):
        assert parse_resume_id("https://hh.ru/vacancy/12345") is None


# ---------------------------------------------------------------------------
# Dispatcher tests
# ---------------------------------------------------------------------------


async def _create_candidate(
    *,
    status: CandidateStatus = CandidateStatus.TEST1_COMPLETED,
    hh_negotiation_id: str = None,
    hh_vacancy_id: str = None,
) -> int:
    """Create a test candidate and return their users.id."""
    tg_id = next(_tg_counter)
    async with async_session() as session:
        user = User(
            telegram_id=tg_id,
            fio=f"HH Test User {tg_id}",
            city="Test City",
            is_active=True,
            candidate_status=status,
            hh_negotiation_id=hh_negotiation_id,
            hh_vacancy_id=hh_vacancy_id,
        )
        session.add(user)
        await session.commit()
        return user.id


class TestDispatcher:
    @pytest.mark.asyncio
    async def test_dispatch_creates_outbox_when_linked(self):
        """Dispatch should create an outbox entry when candidate has hh_negotiation_id."""
        from backend.domain.hh_sync.dispatcher import dispatch_hh_status_sync

        user_id = await _create_candidate(
            status=CandidateStatus.WAITING_SLOT,
            hh_negotiation_id="neg_123",
            hh_vacancy_id="vac_456",
        )

        async with async_session() as session:
            user = await session.get(User, user_id)
            result = await dispatch_hh_status_sync(
                user,
                CandidateStatus.INTERVIEW_SCHEDULED,
                session=session,
            )
            await session.commit()

        assert result is not None  # outbox ID returned

        # Verify outbox entry was created
        async with async_session() as session:
            outbox = await session.execute(
                select(OutboxNotification).where(
                    OutboxNotification.type == "hh_status_sync",
                    OutboxNotification.id == result,
                )
            )
            entry = outbox.scalar_one()
            assert entry.payload_json["negotiation_id"] == "neg_123"
            assert entry.payload_json["target_status"] == "invitation"
            assert entry.payload_json["candidate_id"] == user_id

        # Verify sync log was created
        async with async_session() as session:
            logs = await session.execute(
                select(HHSyncLog).where(HHSyncLog.candidate_id == user_id)
            )
            log_entry = logs.scalar_one()
            assert log_entry.event_type == "status_sync"
            assert log_entry.hh_status == "invitation"
            assert log_entry.status == "pending"

    @pytest.mark.asyncio
    async def test_dispatch_skips_when_no_negotiation_id(self):
        """Dispatch should skip candidates without hh_negotiation_id."""
        from backend.domain.hh_sync.dispatcher import dispatch_hh_status_sync

        user_id = await _create_candidate(
            status=CandidateStatus.WAITING_SLOT,
            hh_negotiation_id=None,
        )

        async with async_session() as session:
            user = await session.get(User, user_id)
            result = await dispatch_hh_status_sync(
                user,
                CandidateStatus.INTERVIEW_SCHEDULED,
                session=session,
            )
            await session.commit()

        assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_skips_internal_status(self):
        """Dispatch should skip statuses that don't map to hh.ru."""
        from backend.domain.hh_sync.dispatcher import dispatch_hh_status_sync

        user_id = await _create_candidate(
            status=CandidateStatus.TEST1_COMPLETED,
            hh_negotiation_id="neg_789",
        )

        async with async_session() as session:
            user = await session.get(User, user_id)
            result = await dispatch_hh_status_sync(
                user,
                CandidateStatus.WAITING_SLOT,
                session=session,
            )
            await session.commit()

        assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_sets_pending_sync_status(self):
        """Dispatch should mark candidate's hh_sync_status as pending."""
        from backend.domain.hh_sync.dispatcher import dispatch_hh_status_sync

        user_id = await _create_candidate(
            status=CandidateStatus.WAITING_SLOT,
            hh_negotiation_id="neg_abc",
        )

        async with async_session() as session:
            user = await session.get(User, user_id)
            await dispatch_hh_status_sync(
                user,
                CandidateStatus.HIRED,
                session=session,
            )
            await session.commit()

        async with async_session() as session:
            user = await session.get(User, user_id)
            assert user.hh_sync_status == "pending"


# ---------------------------------------------------------------------------
# Callback handler tests
# ---------------------------------------------------------------------------


class TestCallbackHandlers:
    @pytest.mark.asyncio
    async def test_sync_callback_success(self):
        """Successful callback should mark candidate as synced."""
        from backend.domain.hh_sync.worker import handle_sync_callback

        user_id = await _create_candidate(
            status=CandidateStatus.INTERVIEW_SCHEDULED,
            hh_negotiation_id="neg_sync_ok",
        )

        # First create a pending sync log
        async with async_session() as session:
            sync_log = HHSyncLog(
                candidate_id=user_id,
                event_type="status_sync",
                rs_status="interview_scheduled",
                hh_status="invitation",
                status="pending",
            )
            session.add(sync_log)
            await session.commit()

        # Handle callback
        async with async_session() as session:
            await handle_sync_callback(
                candidate_id=user_id,
                success=True,
                hh_status="invitation",
                session=session,
            )
            await session.commit()

        # Verify candidate state
        async with async_session() as session:
            user = await session.get(User, user_id)
            assert user.hh_sync_status == "synced"
            assert user.hh_sync_error is None
            assert user.hh_synced_at is not None

    @pytest.mark.asyncio
    async def test_sync_callback_error(self):
        """Error callback should mark candidate sync as error."""
        from backend.domain.hh_sync.worker import handle_sync_callback

        user_id = await _create_candidate(
            status=CandidateStatus.INTERVIEW_SCHEDULED,
            hh_negotiation_id="neg_sync_err",
        )

        async with async_session() as session:
            await handle_sync_callback(
                candidate_id=user_id,
                success=False,
                error_message="hh.ru API returned 403",
                session=session,
            )
            await session.commit()

        async with async_session() as session:
            user = await session.get(User, user_id)
            assert user.hh_sync_status == "error"
            assert "403" in user.hh_sync_error

    @pytest.mark.asyncio
    async def test_resolve_callback_found(self):
        """Resolve callback with negotiation_id should link candidate."""
        from backend.domain.hh_sync.worker import handle_resolve_callback

        user_id = await _create_candidate(
            status=CandidateStatus.TEST1_COMPLETED,
        )

        async with async_session() as session:
            await handle_resolve_callback(
                candidate_id=user_id,
                negotiation_id="neg_resolved_123",
                vacancy_id="vac_resolved_456",
                session=session,
            )
            await session.commit()

        async with async_session() as session:
            user = await session.get(User, user_id)
            assert user.hh_negotiation_id == "neg_resolved_123"
            assert user.hh_vacancy_id == "vac_resolved_456"
            assert user.hh_sync_status == "synced"

    @pytest.mark.asyncio
    async def test_resolve_callback_not_found(self):
        """Resolve callback with not_found should set skipped status."""
        from backend.domain.hh_sync.worker import handle_resolve_callback

        user_id = await _create_candidate(
            status=CandidateStatus.TEST1_COMPLETED,
        )

        async with async_session() as session:
            await handle_resolve_callback(
                candidate_id=user_id,
                not_found=True,
                session=session,
            )
            await session.commit()

        async with async_session() as session:
            user = await session.get(User, user_id)
            assert user.hh_negotiation_id is None
            assert user.hh_sync_status == "skipped"
