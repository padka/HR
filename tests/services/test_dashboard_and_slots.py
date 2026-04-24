from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.apps.admin_ui.services.dashboard import (
    dashboard_counts,
    get_recruiter_leaderboard,
    get_waiting_candidates,
    get_waiting_candidates_payload,
)
from backend.apps.admin_ui.security import Principal
from backend.apps.admin_ui.services.reschedule_intents import get_candidate_reschedule_intent
from backend.apps.admin_ui.services.slots import api_slots_payload, create_slot, list_slots
from backend.core.db import async_session
from backend.domain.ai.models import AIOutput
from backend.domain import models
from backend.domain.candidates.models import User
from backend.domain.candidates.status import CandidateStatus
from backend.domain.repositories import reject_slot
from backend.apps.bot.metrics import (
    record_test1_completion,
    record_test1_rejection,
    reset_test1_metrics,
)


@pytest.mark.asyncio
async def test_waiting_candidates_list_is_capped_to_hundred(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")

    async with async_session() as session:
        city = models.City(name="Incoming City", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)

        now = datetime.now(timezone.utc)
        users = []
        for idx in range(130):
            users.append(
                User(
                    fio=f"Incoming Candidate {idx}",
                    city="Incoming City",
                    telegram_id=900000 + idx,
                    candidate_status=CandidateStatus.WAITING_SLOT,
                    status_changed_at=now - timedelta(minutes=idx),
                    last_activity=now - timedelta(minutes=idx),
                    is_active=True,
                )
            )
        session.add_all(users)
        await session.commit()

    default_items = await get_waiting_candidates()
    explicit_items = await get_waiting_candidates(limit=500)
    payload = await get_waiting_candidates_payload(limit=500)

    assert len(default_items) == 100
    assert len(explicit_items) == 100
    assert payload["queue_total"] == 130
    assert payload["total"] == 130
    assert len(payload["items"]) == 100
    assert payload["page"] == 1
    assert payload["page_size"] == 100
    assert payload["returned_count"] == 100
    assert payload["has_next"] is True
    assert payload["has_prev"] is False
    assert payload["sort"] == "priority"


@pytest.mark.asyncio
async def test_waiting_candidates_payload_recomputes_when_cached_shape_is_incomplete(monkeypatch):
    monkeypatch.delenv("PERF_CACHE_BYPASS", raising=False)

    async with async_session() as session:
        city = models.City(name="Incoming Legacy Cache City", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()

        candidate = User(
            fio="Legacy Cache Candidate",
            city="Incoming Legacy Cache City",
            telegram_id=910001,
            candidate_status=CandidateStatus.WAITING_SLOT,
            status_changed_at=datetime.now(timezone.utc) - timedelta(hours=3),
            last_activity=datetime.now(timezone.utc) - timedelta(hours=3),
            is_active=True,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

    async def fake_get_or_compute(*_args, **_kwargs):
        return {
            "items": [{"id": candidate.id, "name": candidate.fio}],
            "total": 1,
        }

    async def fake_set_cached(*_args, **_kwargs):
        return None

    monkeypatch.setattr("backend.apps.admin_ui.services.dashboard.get_or_compute", fake_get_or_compute)
    monkeypatch.setattr("backend.apps.admin_ui.services.dashboard.set_cached", fake_set_cached)

    payload = await get_waiting_candidates_payload(page=1, page_size=50)

    assert payload["queue_total"] == 1
    assert payload["total"] == 1
    assert payload["returned_count"] == 1
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert payload["items"][0]["id"] == candidate.id


@pytest.mark.asyncio
async def test_waiting_candidates_marks_requested_another_time(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming City 2", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Incoming Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        candidate = User(
            fio="Requested Candidate",
            city="Incoming City 2",
            telegram_id=920001,
            candidate_id="requested-candidate",
            candidate_status=CandidateStatus.WAITING_SLOT,
            status_changed_at=now - timedelta(hours=5),
            last_activity=now - timedelta(hours=5),
            is_active=True,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.PENDING,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        assignment = models.SlotAssignment(
            slot_id=slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.RESCHEDULE_REQUESTED,
            offered_at=now - timedelta(hours=4),
            reschedule_requested_at=now - timedelta(hours=2),
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        session.add(
            models.RescheduleRequest(
                slot_assignment_id=assignment.id,
                requested_start_utc=now + timedelta(days=1, hours=2),
                requested_end_utc=now + timedelta(days=1, hours=4),
                requested_tz="Europe/Moscow",
                candidate_comment="Подходит только вечер",
                status=models.RescheduleRequestStatus.PENDING,
            )
        )
        await session.commit()

    items = await get_waiting_candidates(limit=20)
    row = next(item for item in items if item["id"] == candidate.id)
    assert row["requested_another_time"] is True
    assert row["incoming_substatus"] == "requested_other_time"
    assert row["status_display"] == "Запросил другое время"
    assert row["status_color"] == "warning"
    assert row["requested_another_time_comment"] == "Подходит только вечер"
    assert row["requested_another_time_from"] is not None
    assert row["requested_another_time_to"] is not None
    assert row["lifecycle_summary"]["stage"] in {"waiting_interview_slot", "interview"}
    assert row["scheduling_summary"]["source"] == "slot_assignment"
    assert row["scheduling_summary"]["status"] == "reschedule_requested"
    assert row["candidate_next_action"]["primary_action"]["type"] == "resolve_reschedule"
    assert row["operational_summary"]["queue_state"] == "requested_other_time"
    assert row["operational_summary"]["requested_reschedule"] is True


@pytest.mark.asyncio
async def test_waiting_candidates_uses_bot_state_for_reschedule_intent(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming City 3", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Incoming Recruiter 3", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        candidate = User(
            fio="Bot State Candidate",
            city="Incoming City 3",
            telegram_id=920002,
            telegram_user_id=920002,
            candidate_id="bot-state-candidate",
            candidate_status=CandidateStatus.SLOT_PENDING,
            status_changed_at=now - timedelta(hours=3),
            last_activity=now - timedelta(hours=3),
            is_active=True,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.PENDING,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        assignment = models.SlotAssignment(
            slot_id=slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
            offered_at=now - timedelta(hours=2),
        )
        session.add(assignment)
        await session.commit()

    class FakeStateManager:
        async def get(self, *_args, **_kwargs):
            raise AssertionError("dashboard/incoming should batch bot-state lookup")

        async def get_many(self, user_ids):
            assert list(user_ids) == [candidate.telegram_user_id]
            return {
                int(candidate.telegram_user_id): {
                    "slot_assignment_state": "waiting_candidate_datetime_input",
                    "slot_assignment_id": assignment.id,
                }
            }

    monkeypatch.setattr(
        "backend.apps.bot.services.get_state_manager",
        lambda: FakeStateManager(),
    )

    items = await get_waiting_candidates(limit=20)
    row = next(item for item in items if item["id"] == candidate.id)
    assert row["requested_another_time"] is True
    assert row["incoming_substatus"] == "requested_other_time"
    assert row["status_display"] == "Запросил другое время"
    assert row["status_color"] == "warning"
    assert row["requested_another_time_from"] is None
    assert row["requested_another_time_to"] is None
    assert row["operational_summary"]["queue_state"] == "requested_other_time"


@pytest.mark.asyncio
async def test_get_candidate_reschedule_intent_prefers_db_over_bot_state(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming City DB First", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Incoming Recruiter DB First", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        candidate = User(
            fio="DB First Candidate",
            city="Incoming City DB First",
            telegram_id=930001,
            telegram_user_id=930001,
            candidate_id="db-first-candidate",
            candidate_status=CandidateStatus.SLOT_PENDING,
            status_changed_at=now - timedelta(hours=3),
            last_activity=now - timedelta(hours=3),
            is_active=True,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.PENDING,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        assignment = models.SlotAssignment(
            slot_id=slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.RESCHEDULE_REQUESTED,
            offered_at=now - timedelta(hours=4),
            reschedule_requested_at=now - timedelta(hours=2),
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        session.add(
            models.RescheduleRequest(
                slot_assignment_id=assignment.id,
                requested_start_utc=now + timedelta(days=1, hours=2),
                requested_end_utc=now + timedelta(days=1, hours=4),
                requested_tz="Europe/Moscow",
                candidate_comment="DB intent wins",
                status=models.RescheduleRequestStatus.PENDING,
            )
        )
        await session.commit()

    class FailingStateManager:
        async def get(self, *_args, **_kwargs):
            raise AssertionError("bot-state fallback should not be used when DB intent exists")

        async def get_many(self, *_args, **_kwargs):
            raise AssertionError("bot-state fallback should not be used when DB intent exists")

    monkeypatch.setattr("backend.apps.bot.services.get_state_manager", lambda: FailingStateManager())

    async with async_session() as session:
        intent = await get_candidate_reschedule_intent(
            session,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
        )

    assert intent is not None
    assert intent.requested is True
    assert intent.source == "pending_request"
    assert intent.candidate_comment == "DB intent wins"


@pytest.mark.asyncio
async def test_waiting_candidates_ignore_expired_ai_outputs(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming City 4", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()
        await session.refresh(city)

        candidate = User(
            fio="AI Incoming Candidate",
            city="Incoming City 4",
            telegram_id=920003,
            candidate_status=CandidateStatus.WAITING_SLOT,
            status_changed_at=now - timedelta(hours=2),
            last_activity=now - timedelta(hours=2),
            is_active=True,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        session.add_all(
            [
                AIOutput(
                    scope_type="candidate",
                    scope_id=candidate.id,
                    kind="candidate_summary_v1",
                    input_hash="valid",
                    payload_json={
                        "fit": {"score": 61, "level": "medium"},
                        "scorecard": {
                            "final_score": 61,
                            "recommendation": "clarify_before_od",
                            "blockers": [],
                            "missing_data": [
                                {
                                    "key": "field_format_readiness",
                                    "label": "Готовность к полевому формату",
                                    "evidence": "Нужно подтвердить формат работы.",
                                }
                            ],
                        },
                    },
                    created_at=now - timedelta(minutes=10),
                    expires_at=now + timedelta(hours=1),
                ),
                AIOutput(
                    scope_type="candidate",
                    scope_id=candidate.id,
                    kind="candidate_summary_v1",
                    input_hash="expired",
                    payload_json={
                        "fit": {"score": 95, "level": "high"},
                        "scorecard": {
                            "final_score": 95,
                            "recommendation": "od_recommended",
                            "blockers": [],
                            "missing_data": [],
                        },
                    },
                    created_at=now - timedelta(minutes=1),
                    expires_at=now - timedelta(seconds=1),
                ),
            ]
        )
        await session.commit()

    items = await get_waiting_candidates(limit=20)
    row = next(item for item in items if item["id"] == candidate.id)
    assert row["ai_relevance_score"] == 61
    assert row["ai_relevance_level"] == "medium"
    assert row["ai_relevance_state"] == "ready"
    assert row["ai_recommendation"] == "clarify_before_od"
    assert row["ai_risk_hint"] == "Готовность к полевому формату"
    assert row["ai_reasons"] == [
        {
            "tone": "missing",
            "label": "Готовность к полевому формату",
        }
    ]


@pytest.mark.asyncio
async def test_waiting_candidates_returns_null_ai_and_schedules_background_warm_when_cache_missing(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")
    scheduled_candidate_ids: list[int] = []

    def fake_schedule(candidate_ids, *, principal=None, refresh=True):
        scheduled_candidate_ids.extend(int(candidate_id) for candidate_id in candidate_ids)
        return None

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.dashboard.schedule_warm_candidates_ai_outputs",
        fake_schedule,
    )

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming City Live AI", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()

        candidate = User(
            fio="Live AI Candidate",
            city="Incoming City Live AI",
            telegram_id=930001,
            candidate_status=CandidateStatus.WAITING_SLOT,
            status_changed_at=now - timedelta(hours=2),
            last_activity=now - timedelta(hours=2),
            is_active=True,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

    items = await get_waiting_candidates(limit=20)
    row = next(item for item in items if item["id"] == candidate.id)
    assert row["ai_relevance_score"] is None
    assert row["ai_relevance_level"] is None
    assert row["ai_relevance_state"] == "warming"
    assert row["ai_recommendation"] is None
    assert row["ai_risk_hint"] is None
    assert row["ai_reasons"] == []
    assert scheduled_candidate_ids == [candidate.id]


@pytest.mark.asyncio
async def test_waiting_candidates_limits_background_ai_warm_budget(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")
    scheduled_candidate_ids: list[int] = []

    def fake_schedule(candidate_ids, *, principal=None, refresh=True):
        scheduled_candidate_ids.extend(int(candidate_id) for candidate_id in candidate_ids)
        return None

    monkeypatch.setattr(
        "backend.apps.admin_ui.services.dashboard.schedule_warm_candidates_ai_outputs",
        fake_schedule,
    )

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming City Warm Budget", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()

        users = []
        for idx in range(12):
            users.append(
                User(
                    fio=f"Warm Budget Candidate {idx}",
                    city="Incoming City Warm Budget",
                    telegram_id=940000 + idx,
                    candidate_status=CandidateStatus.WAITING_SLOT,
                    status_changed_at=now - timedelta(minutes=idx),
                    last_activity=now - timedelta(minutes=idx),
                    is_active=True,
                )
            )
        session.add_all(users)
        await session.commit()

    payload = await get_waiting_candidates_payload(limit=20)
    items = payload["items"]
    assert len(items) == 12
    assert len(scheduled_candidate_ids) == 10
    warming_count = sum(1 for item in items if item["ai_relevance_state"] == "warming")
    unknown_count = sum(1 for item in items if item["ai_relevance_state"] == "unknown")
    assert warming_count == 10
    assert unknown_count == 2


@pytest.mark.asyncio
async def test_waiting_candidates_marks_ai_output_stale_when_candidate_changed_after_snapshot(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming City AI Stale", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()

        candidate = User(
            fio="AI Stale Candidate",
            city="Incoming City AI Stale",
            telegram_id=950001,
            candidate_status=CandidateStatus.WAITING_SLOT,
            status_changed_at=now - timedelta(minutes=5),
            last_activity=now - timedelta(minutes=5),
            is_active=True,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)

        session.add(
            AIOutput(
                scope_type="candidate",
                scope_id=candidate.id,
                kind="candidate_summary_v1",
                input_hash="stale",
                payload_json={
                    "fit": {"score": 88, "level": "high"},
                    "scorecard": {
                        "final_score": 88,
                        "recommendation": "od_recommended",
                        "metrics": [
                            {
                                "key": "field_ready",
                                "label": "Готов к полевому формату",
                                "score": 18,
                                "status": "met",
                                "evidence": "Подтвердил готовность к разъездному формату.",
                            }
                        ],
                        "blockers": [],
                        "missing_data": [],
                    },
                },
                created_at=now - timedelta(hours=2),
                expires_at=now + timedelta(hours=1),
            )
        )
        await session.commit()

    payload = await get_waiting_candidates_payload(limit=20)
    row = next(item for item in payload["items"] if item["id"] == candidate.id)
    assert row["ai_relevance_state"] == "stale"
    assert row["ai_reasons"] == [
        {
            "tone": "positive",
            "label": "Готов к полевому формату",
        }
    ]


@pytest.mark.asyncio
async def test_waiting_candidates_payload_supports_server_side_paging_and_filters(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming City Paging", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()

        session.add_all(
            [
                User(
                    fio="Alice Incoming",
                    city="Incoming City Paging",
                    telegram_id=960001,
                    candidate_status=CandidateStatus.WAITING_SLOT,
                    status_changed_at=now - timedelta(hours=5),
                    last_activity=now - timedelta(hours=5),
                    is_active=True,
                ),
                User(
                    fio="Boris Incoming",
                    city="Incoming City Paging",
                    telegram_id=960002,
                    candidate_status=CandidateStatus.STALLED_WAITING_SLOT,
                    status_changed_at=now - timedelta(hours=30),
                    last_activity=now - timedelta(hours=30),
                    is_active=True,
                ),
                User(
                    fio="Cedric Incoming",
                    city="Incoming City Paging",
                    telegram_id=960003,
                    candidate_status=CandidateStatus.SLOT_PENDING,
                    status_changed_at=now - timedelta(hours=3),
                    last_activity=now - timedelta(hours=3),
                    is_active=True,
                ),
            ]
        )
        await session.commit()

    name_sorted_payload = await get_waiting_candidates_payload(
        page=2,
        page_size=1,
        sort="name_asc",
    )
    assert name_sorted_payload["queue_total"] == 2
    assert name_sorted_payload["total"] == 2
    assert name_sorted_payload["returned_count"] == 1
    assert name_sorted_payload["has_prev"] is True
    assert name_sorted_payload["has_next"] is False
    assert name_sorted_payload["items"][0]["name"] == "Boris Incoming"

    filtered_payload = await get_waiting_candidates_payload(
        page=1,
        page_size=10,
        waiting="24h",
    )
    assert filtered_payload["queue_total"] == 2
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["name"] == "Boris Incoming"


@pytest.mark.asyncio
async def test_waiting_candidates_excludes_slot_pending_without_reschedule_request(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming City Pending Exclusion", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Pending Exclusion Recruiter", tz="Europe/Moscow", active=True)
        recruiter.cities.append(city)
        session.add_all([city, recruiter])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)

        waiting_candidate = User(
            fio="Waiting Slot Candidate",
            city=city.name,
            telegram_id=960101,
            candidate_status=CandidateStatus.WAITING_SLOT,
            status_changed_at=now - timedelta(hours=5),
            last_activity=now - timedelta(hours=5),
            is_active=True,
        )
        pending_candidate = User(
            fio="Selected Slot Candidate",
            city=city.name,
            telegram_id=960102,
            candidate_id="selected-slot-candidate",
            candidate_status=CandidateStatus.SLOT_PENDING,
            status_changed_at=now - timedelta(hours=3),
            last_activity=now - timedelta(hours=3),
            is_active=True,
        )
        session.add_all([waiting_candidate, pending_candidate])
        await session.commit()
        await session.refresh(pending_candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=30,
            status=models.SlotStatus.PENDING,
            candidate_id=pending_candidate.candidate_id,
            candidate_tg_id=pending_candidate.telegram_id,
            candidate_fio=pending_candidate.fio,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        assignment = models.SlotAssignment(
            slot_id=slot.id,
            recruiter_id=recruiter.id,
            candidate_id=pending_candidate.candidate_id,
            candidate_tg_id=pending_candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
            offered_at=now - timedelta(hours=2),
        )
        session.add(assignment)
        await session.commit()

    payload = await get_waiting_candidates_payload(page=1, page_size=20)
    names = {item["name"] for item in payload["items"]}
    assert names == {"Waiting Slot Candidate"}
    assert payload["queue_total"] == 1


@pytest.mark.asyncio
async def test_waiting_candidates_can_filter_by_messenger_channel(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming Channel City", tz="Europe/Moscow", active=True)
        session.add(city)
        await session.commit()

        session.add_all(
            [
                User(
                    fio="Telegram Incoming",
                    city=city.name,
                    telegram_id=980001,
                    messenger_platform="telegram",
                    candidate_status=CandidateStatus.WAITING_SLOT,
                    status_changed_at=now - timedelta(hours=4),
                    last_activity=now - timedelta(hours=4),
                    is_active=True,
                ),
                User(
                    fio="MAX Incoming",
                    city=city.name,
                    messenger_platform="max",
                    max_user_id="max-980002",
                    candidate_status=CandidateStatus.WAITING_SLOT,
                    status_changed_at=now - timedelta(hours=3),
                    last_activity=now - timedelta(hours=3),
                    is_active=True,
                ),
            ]
        )
        await session.commit()

    telegram_payload = await get_waiting_candidates_payload(page=1, page_size=10, channel="telegram")
    assert {item["name"] for item in telegram_payload["items"]} == {"Telegram Incoming"}
    assert {item["messenger_channel"] for item in telegram_payload["items"]} == {"telegram"}

    max_payload = await get_waiting_candidates_payload(page=1, page_size=10, channel="max")
    assert {item["name"] for item in max_payload["items"]} == {"MAX Incoming"}
    assert {item["messenger_channel"] for item in max_payload["items"]} == {"max"}


@pytest.mark.asyncio
async def test_waiting_candidates_payload_keeps_recruiter_visibility_rules(monkeypatch):
    monkeypatch.setenv("PERF_CACHE_BYPASS", "1")

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        city = models.City(name="Incoming City Recruiter Scope", tz="Europe/Moscow", active=True)
        owner = models.Recruiter(name="Owner Recruiter", tz="Europe/Moscow", active=True)
        other = models.Recruiter(name="Other Recruiter", tz="Europe/Moscow", active=True)
        owner.cities.append(city)
        session.add_all([city, owner, other])
        await session.commit()
        await session.refresh(owner)

        session.add_all(
            [
                User(
                    fio="Assigned To Owner",
                    city="Incoming City Recruiter Scope",
                    telegram_id=970001,
                    candidate_status=CandidateStatus.WAITING_SLOT,
                    status_changed_at=now - timedelta(hours=8),
                    last_activity=now - timedelta(hours=8),
                    responsible_recruiter_id=owner.id,
                    is_active=True,
                ),
                User(
                    fio="Unassigned In City",
                    city="Incoming City Recruiter Scope",
                    telegram_id=970002,
                    candidate_status=CandidateStatus.WAITING_SLOT,
                    status_changed_at=now - timedelta(hours=4),
                    last_activity=now - timedelta(hours=4),
                    responsible_recruiter_id=None,
                    is_active=True,
                ),
                User(
                    fio="Assigned To Other",
                    city="Incoming City Recruiter Scope",
                    telegram_id=970003,
                    candidate_status=CandidateStatus.WAITING_SLOT,
                    status_changed_at=now - timedelta(hours=2),
                    last_activity=now - timedelta(hours=2),
                    responsible_recruiter_id=other.id,
                    is_active=True,
                ),
            ]
        )
        await session.commit()

    payload = await get_waiting_candidates_payload(
        page=1,
        page_size=10,
        principal=Principal(type="recruiter", id=owner.id),
    )
    assert payload["queue_total"] == 2
    assert payload["total"] == 2
    names = {item["name"] for item in payload["items"]}
    assert names == {"Assigned To Owner", "Unassigned In City"}


@pytest.mark.asyncio
async def test_dashboard_and_slot_listing():
    await reset_test1_metrics()
    async with async_session() as session:
        recruiter = models.Recruiter(name="UI", tz="Europe/Moscow", active=True)
        city = models.City(name="UI City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
        await session.refresh(city)

    target_day = date.today() + timedelta(days=1)
    created = await create_slot(
        recruiter_id=recruiter.id,
        date=str(target_day),
        time="10:00",
        city_id=city.id,
    )
    assert created is True

    counts = await dashboard_counts()
    assert counts["recruiters"] == 1
    assert counts["cities"] == 1
    assert counts["slots_total"] == 1
    assert counts["test1_rejections_total"] == 0
    assert counts["test1_rejections_percent"] == 0.0

    listing = await list_slots(
        recruiter_id=None,
        status=None,
        page=1,
        per_page=10,
    )
    assert listing["total"] == 1
    assert listing["items"][0].recruiter_id == recruiter.id
    assert listing["status_counts"] == {"FREE": 1, "CONFIRMED_BY_CANDIDATE": 0}


@pytest.mark.asyncio
async def test_dashboard_reports_test1_metrics():
    await reset_test1_metrics()
    await record_test1_rejection("format_not_ready")
    await record_test1_completion()

    counts = await dashboard_counts()
    assert counts["test1_rejections_total"] == 1
    assert counts["test1_total_seen"] == 2
    assert counts["test1_rejections_percent"] == 50.0
    assert counts["test1_rejections_breakdown"]["format_not_ready"] == 1


@pytest.mark.asyncio
async def test_slots_list_status_counts_and_api_payload_normalizes_statuses():
    async with async_session() as session:
        recruiter = models.Recruiter(name="UI", tz="Europe/Moscow", active=True)
        city = models.City(name="City", tz="Europe/Moscow", active=True)
        session.add_all([recruiter, city])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        city.responsible_recruiter_id = recruiter.id
        await session.commit()
        await session.refresh(city)

        now = datetime.now(timezone.utc)
        session.add_all(
            [
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now,
                    status=models.SlotStatus.FREE,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now + timedelta(hours=1),
                    status=models.SlotStatus.PENDING,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now + timedelta(hours=2),
                    status=models.SlotStatus.BOOKED,
                ),
                models.Slot(
                    recruiter_id=recruiter.id,
                    city_id=city.id,
                    start_utc=now + timedelta(hours=3),
                    status=models.SlotStatus.CONFIRMED_BY_CANDIDATE,
                ),
            ]
        )
        await session.commit()

    payload = await api_slots_payload(recruiter_id=None, status=None, limit=10)
    assert {item["status"] for item in payload} == {
        "FREE",
        "PENDING",
        "BOOKED",
        "CONFIRMED_BY_CANDIDATE",
    }

    # slots_list now redirects to SPA, test status_counts via list_slots service
    listing = await list_slots(recruiter_id=None, status=None, page=1, per_page=10)
    assert listing["total"] == 4
    assert listing["status_counts"]["FREE"] == 1
    assert listing["status_counts"]["PENDING"] == 1
    assert listing["status_counts"]["BOOKED"] == 1
    assert listing["status_counts"]["CONFIRMED_BY_CANDIDATE"] == 1


@pytest.mark.asyncio
async def test_recruiter_leaderboard_scores_and_ranking():
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        recruiter_a = models.Recruiter(name="Alpha", tz="Europe/Moscow", active=True)
        recruiter_b = models.Recruiter(name="Beta", tz="Europe/Moscow", active=True)
        session.add_all([recruiter_a, recruiter_b])
        await session.commit()
        await session.refresh(recruiter_a)
        await session.refresh(recruiter_b)

        base_time = now - timedelta(days=1)

        def _user(name: str, recruiter_id: int, status: CandidateStatus) -> User:
            return User(
                fio=name,
                responsible_recruiter_id=recruiter_id,
                candidate_status=status,
                status_changed_at=base_time,
                last_activity=base_time,
                city="Moscow",
            )

        users = [
            _user("A1", recruiter_a.id, CandidateStatus.INTERVIEW_SCHEDULED),
            _user("A2", recruiter_a.id, CandidateStatus.INTERVIEW_SCHEDULED),
            _user("A3", recruiter_a.id, CandidateStatus.INTERVIEW_SCHEDULED),
            _user("A4", recruiter_a.id, CandidateStatus.INTERVIEW_SCHEDULED),
            _user("A5", recruiter_a.id, CandidateStatus.INTRO_DAY_SCHEDULED),
            _user("A6", recruiter_a.id, CandidateStatus.HIRED),
            _user("A7", recruiter_a.id, CandidateStatus.HIRED),
            _user("A8", recruiter_a.id, CandidateStatus.NOT_HIRED),
            _user("A9", recruiter_a.id, CandidateStatus.TEST2_FAILED),
            _user("A10", recruiter_a.id, CandidateStatus.WAITING_SLOT),
            _user("B1", recruiter_b.id, CandidateStatus.INTERVIEW_SCHEDULED),
            _user("B2", recruiter_b.id, CandidateStatus.WAITING_SLOT),
            _user("B3", recruiter_b.id, CandidateStatus.WAITING_SLOT),
            _user("B4", recruiter_b.id, CandidateStatus.NOT_HIRED),
            _user("B5", recruiter_b.id, CandidateStatus.TEST2_FAILED),
        ]
        session.add_all(users)

        slots = []
        for idx in range(6):
            status = models.SlotStatus.BOOKED if idx < 3 else models.SlotStatus.CONFIRMED_BY_CANDIDATE
            slots.append(
                models.Slot(
                    recruiter_id=recruiter_a.id,
                    start_utc=now - timedelta(hours=idx + 1),
                    status=status,
                )
            )
        for idx in range(2):
            slots.append(
                models.Slot(
                    recruiter_id=recruiter_a.id,
                    start_utc=now - timedelta(hours=idx + 10),
                    status=models.SlotStatus.PENDING,
                )
            )
        for idx in range(2):
            slots.append(
                models.Slot(
                    recruiter_id=recruiter_a.id,
                    start_utc=now - timedelta(hours=idx + 20),
                    status=models.SlotStatus.FREE,
                )
            )
        slots.append(
            models.Slot(
                recruiter_id=recruiter_b.id,
                start_utc=now - timedelta(hours=2),
                status=models.SlotStatus.BOOKED,
            )
        )
        for idx in range(4):
            slots.append(
                models.Slot(
                    recruiter_id=recruiter_b.id,
                    start_utc=now - timedelta(hours=idx + 6),
                    status=models.SlotStatus.FREE,
                )
            )
        session.add_all(slots)
        await session.commit()

    payload = await get_recruiter_leaderboard(
        date_from=now - timedelta(days=7),
        date_to=now,
    )
    items = payload["items"]
    assert len(items) == 2

    item_a = next(item for item in items if item["recruiter_id"] == recruiter_a.id)
    item_b = next(item for item in items if item["recruiter_id"] == recruiter_b.id)

    assert item_a["candidates_total"] == 10
    assert item_a["slots_booked"] == 6
    assert item_a["fill_rate"] == 60.0
    assert item_a["conversion_interview"] == 70.0
    assert item_a["score"] >= item_b["score"]
    assert item_a["rank"] == 1


@pytest.mark.asyncio
async def test_api_slots_payload_uses_assignment_fallback_for_legacy_free_slot():
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        recruiter = models.Recruiter(name="Legacy Recruiter", tz="Europe/Moscow", active=True)
        city = models.City(name="Legacy City", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Legacy Candidate",
            city="Legacy City",
            telegram_id=901001,
            candidate_status=CandidateStatus.TEST1_COMPLETED,
        )
        session.add_all([recruiter, city, candidate])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=3),
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        assignment = models.SlotAssignment(
            slot_id=slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add(assignment)
        await session.commit()

        slot_id = slot.id
        candidate_fio = candidate.fio
        recruiter_id = recruiter.id

    payload = await api_slots_payload(recruiter_id=recruiter_id, status=None, limit=10)
    row = next(item for item in payload if item["id"] == slot_id)
    assert row["status"] == "PENDING"
    assert row["candidate_fio"] == candidate_fio


@pytest.mark.asyncio
async def test_api_slots_payload_keeps_recruiter_and_candidate_timezones_separate():
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    async with async_session() as session:
        recruiter = models.Recruiter(name="TZ Recruiter", tz="Europe/Moscow", active=True)
        city = models.City(name="Almaty City", tz="Asia/Almaty", active=True)
        candidate = User(
            fio="TZ Candidate",
            city="Almaty City",
            telegram_id=901777,
            candidate_status=CandidateStatus.TEST1_COMPLETED,
        )
        session.add_all([recruiter, city, candidate])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=1),
            status=models.SlotStatus.FREE,
            tz_name="Asia/Almaty",
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        assignment = models.SlotAssignment(
            slot_id=slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Asia/Almaty",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add(assignment)
        await session.commit()

        recruiter_id = recruiter.id
        slot_id = slot.id

    payload = await api_slots_payload(recruiter_id=recruiter_id, status=None, limit=10)
    row = next(item for item in payload if item["id"] == slot_id)

    assert row["recruiter_tz"] == "Europe/Moscow"
    assert row["candidate_tz"] == "Asia/Almaty"
    assert row["recruiter_local_time"].endswith("+03:00")
    assert row["candidate_local_time"].endswith("+05:00")


@pytest.mark.asyncio
async def test_reject_slot_cancels_active_assignment_and_disables_fallback():
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        recruiter = models.Recruiter(name="Reject Recruiter", tz="Europe/Moscow", active=True)
        city = models.City(name="Reject City", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Reject Candidate",
            city="Reject City",
            telegram_id=902001,
            candidate_status=CandidateStatus.INTERVIEW_CONFIRMED,
        )
        session.add_all([recruiter, city, candidate])
        await session.commit()
        await session.refresh(recruiter)
        await session.refresh(city)
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(hours=4),
            status=models.SlotStatus.BOOKED,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        assignment = models.SlotAssignment(
            slot_id=slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.CONFIRMED,
            confirmed_at=now,
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        session.add_all(
            [
                models.ActionToken(
                    token="reject-confirm-token",
                    action="slot_assignment_confirm",
                    entity_id=str(assignment.id),
                    expires_at=now + timedelta(hours=2),
                    created_at=now,
                ),
                models.ActionToken(
                    token="reject-reschedule-token",
                    action="slot_assignment_reschedule_request",
                    entity_id=str(assignment.id),
                    expires_at=now + timedelta(hours=2),
                    created_at=now,
                ),
            ]
        )
        await session.commit()

        slot_id = slot.id
        assignment_id = assignment.id
        recruiter_id = recruiter.id

    await reject_slot(slot_id)

    async with async_session() as session:
        slot = await session.get(models.Slot, slot_id)
        assignment = await session.get(models.SlotAssignment, assignment_id)
        assert slot is not None
        assert assignment is not None
        assert slot.status == models.SlotStatus.FREE
        assert slot.candidate_id is None
        assert slot.candidate_tg_id is None
        assert assignment.status == models.SlotAssignmentStatus.CANCELLED
        assert assignment.cancelled_at is not None

        tokens = list(
            await session.scalars(
                select(models.ActionToken).where(models.ActionToken.entity_id == str(assignment_id))
            )
        )
        assert tokens
        assert all(token.used_at is not None for token in tokens)

    payload = await api_slots_payload(recruiter_id=recruiter_id, status=None, limit=10)
    row = next(item for item in payload if item["id"] == slot_id)
    assert row["status"] == "FREE"
    assert row["candidate_tg_id"] is None
