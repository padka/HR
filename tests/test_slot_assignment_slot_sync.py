from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.apps.admin_ui.routers.slot_assignments_api import ActionPayload, confirm_assignment
from backend.core.db import async_session
from backend.domain import models
from backend.domain.candidates.models import User
from backend.domain.repositories import confirm_slot_by_candidate
from backend.domain.scheduling_repair_service import repair_slot_assignment_scheduling_conflict
from backend.domain.slot_assignment_service import create_slot_assignment


@pytest.mark.asyncio
async def test_create_slot_assignment_syncs_slot_candidate_binding():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        city = models.City(name="Sync City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Sync Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Тест Слота",
            city="Sync City",
            telegram_id=710001,
            username="sync_candidate",
        )
        slot = models.Slot(
            recruiter_id=1,
            city_id=1,
            start_utc=now + timedelta(days=1),
            duration_min=30,
            status=models.SlotStatus.FREE,
        )
        session.add_all([city, recruiter, candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        slot.recruiter_id = recruiter.id
        slot.city_id = city.id
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        slot_id = slot.id
        candidate_id = candidate.candidate_id
        candidate_tg_id = candidate.telegram_id
        candidate_fio = candidate.fio

    result = await create_slot_assignment(
        slot_id=slot_id,
        candidate_id=candidate_id,
        created_by="test",
    )
    assert result.ok is True

    async with async_session() as session:
        slot = await session.get(models.Slot, slot_id)
        assert slot is not None
        assert slot.status == models.SlotStatus.PENDING
        assert slot.candidate_id == candidate_id
        assert slot.candidate_tg_id == candidate_tg_id
        assert slot.candidate_fio == candidate_fio


@pytest.mark.asyncio
async def test_confirm_assignment_accepts_telegram_user_id_and_updates_slot():
    now = datetime.now(timezone.utc)
    telegram_id = 720001
    telegram_user_id = 720002

    async with async_session() as session:
        city = models.City(name="Confirm City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Confirm Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Подтвержденный Кандидат",
            city="Confirm City",
            telegram_id=telegram_id,
            telegram_user_id=telegram_user_id,
            username="confirm_candidate",
        )
        session.add_all([city, recruiter, candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            start_utc=now + timedelta(days=1),
            duration_min=30,
            status=models.SlotStatus.FREE,
        )
        session.add(slot)
        await session.commit()
        await session.refresh(slot)

        assignment = models.SlotAssignment(
            slot_id=slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        token_value = "sync-confirm-token"
        session.add(
            models.ActionToken(
                token=token_value,
                action="slot_assignment_confirm",
                entity_id=str(assignment.id),
                expires_at=now + timedelta(hours=2),
                created_at=now,
            )
        )
        await session.commit()

        assignment_id = assignment.id
        slot_id = slot.id
        candidate_uuid = candidate.candidate_id

    result = await confirm_assignment(
        assignment_id,
        ActionPayload(action_token=token_value, candidate_tg_id=telegram_user_id),
    )
    assert result["ok"] is True

    async with async_session() as session:
        assignment = await session.get(models.SlotAssignment, assignment_id)
        slot = await session.get(models.Slot, slot_id)
        candidate = await session.scalar(
            select(User).where(User.candidate_id == candidate_uuid)
        )
        assert assignment is not None
        assert assignment.status == models.SlotAssignmentStatus.CONFIRMED
        assert assignment.candidate_tg_id == telegram_user_id
        assert slot is not None
        assert slot.status == models.SlotStatus.BOOKED
        assert slot.candidate_tg_id == telegram_user_id
        assert slot.candidate_id == candidate_uuid
        assert candidate is not None
        assert candidate.responsible_recruiter_id == recruiter.id


@pytest.mark.asyncio
async def test_repair_assignment_authoritative_releases_stale_slot_and_restores_consistency():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        city = models.City(name="Repair City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Repair Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Repair Candidate",
            city="Repair City",
            telegram_id=730001,
            telegram_user_id=730001,
            username="repair_candidate",
        )
        session.add_all([city, recruiter, candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        await session.refresh(candidate)

        stale_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        target_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add_all([stale_slot, target_slot])
        await session.commit()
        await session.refresh(stale_slot)
        await session.refresh(target_slot)

        assignment = models.SlotAssignment(
            slot_id=target_slot.id,
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

        stale_slot_id = stale_slot.id
        target_slot_id = target_slot.id
        assignment_id = assignment.id

    result = await repair_slot_assignment_scheduling_conflict(
        assignment_id=assignment_id,
        repair_action="assignment_authoritative",
        performed_by_type="admin",
        performed_by_id=0,
    )
    assert result.ok is True
    assert result.status == "repaired"
    assert result.payload["released_slot_ids"] == [stale_slot_id]
    assert result.payload["integrity_state"] == "consistent"
    assert result.payload["write_behavior"] == "allow"
    assert result.payload["repairability"] == "not_needed"

    async with async_session() as session:
        stale_slot = await session.get(models.Slot, stale_slot_id)
        target_slot = await session.get(models.Slot, target_slot_id)
        assignment = await session.get(models.SlotAssignment, assignment_id)
        audit_log = await session.scalar(
            select(models.AuditLog).where(
                models.AuditLog.action == "scheduling_repair.assignment_authoritative",
                models.AuditLog.entity_id == str(assignment_id),
            )
        )
        assert stale_slot is not None
        assert stale_slot.status == models.SlotStatus.FREE
        assert stale_slot.candidate_id is None
        assert target_slot is not None
        assert target_slot.status == models.SlotStatus.BOOKED
        assert target_slot.candidate_id == assignment.candidate_id
        assert target_slot.candidate_tg_id == assignment.candidate_tg_id
        assert assignment is not None
        assert assignment.status == models.SlotAssignmentStatus.CONFIRMED
        assert audit_log is not None
        assert audit_log.changes["released_slot_ids"] == [stale_slot_id]
        assert audit_log.changes["issue_codes_before"] == ["scheduling_split_brain"]


@pytest.mark.asyncio
async def test_repair_assignment_authoritative_rejects_transitional_split_brain():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        city = models.City(name="Repair Manual City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Repair Manual Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Repair Manual Candidate",
            city="Repair Manual City",
            telegram_id=730002,
            telegram_user_id=730002,
            username="repair_manual_candidate",
        )
        session.add_all([city, recruiter, candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        await session.refresh(candidate)

        stale_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        target_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.FREE,
            purpose="interview",
        )
        session.add_all([stale_slot, target_slot])
        await session.commit()
        await session.refresh(target_slot)

        assignment = models.SlotAssignment(
            slot_id=target_slot.id,
            recruiter_id=recruiter.id,
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)
        assignment_id = assignment.id

    result = await repair_slot_assignment_scheduling_conflict(
        assignment_id=assignment_id,
        repair_action="assignment_authoritative",
        performed_by_type="admin",
        performed_by_id=0,
    )
    assert result.ok is False
    assert result.status == "repair_not_allowed"
    assert result.status_code == 409


@pytest.mark.asyncio
async def test_manual_resolve_to_active_assignment_cancels_duplicates_and_restores_consistency():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        city = models.City(name="Manual Resolve City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Manual Resolve Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Manual Resolve Candidate",
            city="Manual Resolve City",
            telegram_id=730010,
            telegram_user_id=730010,
            username="manual_resolve_candidate",
        )
        session.add_all([city, recruiter, candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        await session.refresh(candidate)

        first_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.PENDING,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        second_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.PENDING,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        session.add_all([first_slot, second_slot])
        await session.commit()
        await session.refresh(first_slot)
        await session.refresh(second_slot)

        first_assignment = models.SlotAssignment(
            slot_id=first_slot.id,
            recruiter_id=recruiter.id,
            candidate_id=None,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        second_assignment = models.SlotAssignment(
            slot_id=second_slot.id,
            recruiter_id=recruiter.id,
            candidate_id=None,
            candidate_tg_id=candidate.telegram_id,
            candidate_tz="Europe/Moscow",
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add_all([first_assignment, second_assignment])
        await session.commit()
        await session.refresh(first_assignment)
        await session.refresh(second_assignment)

        first_slot_id = first_slot.id
        second_slot_id = second_slot.id
        first_assignment_id = first_assignment.id
        second_assignment_id = second_assignment.id

    result = await repair_slot_assignment_scheduling_conflict(
        assignment_id=first_assignment_id,
        repair_action="resolve_to_active_assignment",
        chosen_assignment_id=second_assignment_id,
        confirmations=[
            "selected_assignment_is_canonical",
            "cancel_non_selected_active_assignments",
        ],
        note="keep latest offer",
        performed_by_type="admin",
        performed_by_id=0,
    )
    assert result.ok is True
    assert result.status == "repaired"
    assert result.payload["selected_assignment_id"] == second_assignment_id
    assert result.payload["cancelled_assignment_ids"] == [first_assignment_id]
    assert result.payload["released_slot_ids"] == [first_slot_id]
    assert result.payload["result_state"]["scheduling_summary"]["integrity_state"] == "consistent"
    assert result.payload["repairability"] == "not_needed"

    async with async_session() as session:
        first_assignment = await session.get(models.SlotAssignment, first_assignment_id)
        second_assignment = await session.get(models.SlotAssignment, second_assignment_id)
        first_slot = await session.get(models.Slot, first_slot_id)
        second_slot = await session.get(models.Slot, second_slot_id)
        audit_log = await session.scalar(
            select(models.AuditLog).where(
                models.AuditLog.action == "scheduling_repair.manual_resolution",
                models.AuditLog.entity_id == str(second_assignment_id),
            )
        )
        assert first_assignment is not None
        assert first_assignment.status == models.SlotAssignmentStatus.CANCELLED
        assert second_assignment is not None
        assert second_assignment.status == models.SlotAssignmentStatus.OFFERED
        assert first_slot is not None
        assert first_slot.status == models.SlotStatus.FREE
        assert second_slot is not None
        assert second_slot.status == models.SlotStatus.PENDING
        assert audit_log is not None
        assert audit_log.changes["selected_assignment_id"] == second_assignment_id
        assert audit_log.changes["cancelled_assignment_ids"] == [first_assignment_id]
        assert audit_log.changes["released_slot_ids"] == [first_slot_id]


@pytest.mark.asyncio
async def test_manual_cancel_active_assignment_clears_broken_assignment_owner():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        city = models.City(name="Manual Cancel City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Manual Cancel Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Manual Cancel Candidate",
            city="Manual Cancel City",
            telegram_id=730011,
            telegram_user_id=730011,
            username="manual_cancel_candidate",
        )
        another_candidate = User(
            fio="Occupied Candidate",
            city="Manual Cancel City",
            telegram_id=730012,
            telegram_user_id=730012,
            username="manual_cancel_occupied",
        )
        session.add_all([city, recruiter, candidate, another_candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        await session.refresh(candidate)
        await session.refresh(another_candidate)

        occupied_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=another_candidate.candidate_id,
            candidate_tg_id=another_candidate.telegram_id,
            candidate_fio=another_candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        own_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        session.add_all([occupied_slot, own_slot])
        await session.commit()
        await session.refresh(occupied_slot)
        await session.refresh(own_slot)

        assignment = models.SlotAssignment(
            slot_id=occupied_slot.id,
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

        assignment_id = assignment.id
        occupied_slot_id = occupied_slot.id
        own_slot_id = own_slot.id

    result = await repair_slot_assignment_scheduling_conflict(
        assignment_id=assignment_id,
        repair_action="cancel_active_assignment",
        confirmations=[
            "cancel_active_assignment",
            "candidate_loses_assignment_owned_schedule",
        ],
        note="invalid owner",
        performed_by_type="admin",
        performed_by_id=0,
    )
    assert result.ok is True
    assert result.status == "repaired"
    assert result.payload["cancelled_assignment_ids"] == [assignment_id]
    assert result.payload["result_state"]["scheduling_summary"]["write_owner"] == "slot"
    assert result.payload["repairability"] == "not_needed"

    async with async_session() as session:
        assignment = await session.get(models.SlotAssignment, assignment_id)
        occupied_slot = await session.get(models.Slot, occupied_slot_id)
        own_slot = await session.get(models.Slot, own_slot_id)
        audit_log = await session.scalar(
            select(models.AuditLog).where(
                models.AuditLog.action == "scheduling_repair.manual_resolution",
                models.AuditLog.entity_id == str(assignment_id),
            )
        )
        assert assignment is not None
        assert assignment.status == models.SlotAssignmentStatus.CANCELLED
        assert occupied_slot is not None
        assert occupied_slot.candidate_id == another_candidate.candidate_id
        assert own_slot is not None
        assert own_slot.status == models.SlotStatus.BOOKED
        assert own_slot.candidate_id == candidate.candidate_id
        assert audit_log is not None
        assert audit_log.changes["repair_action"] == "cancel_active_assignment"
        assert audit_log.changes["cancelled_assignment_ids"] == [assignment_id]


@pytest.mark.asyncio
async def test_manual_rebind_assignment_slot_restores_candidate_owned_pairing():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        city = models.City(name="Manual Rebind City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Manual Rebind Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Manual Rebind Candidate",
            city="Manual Rebind City",
            telegram_id=730013,
            telegram_user_id=730013,
            username="manual_rebind_candidate",
        )
        another_candidate = User(
            fio="Wrong Slot Candidate",
            city="Manual Rebind City",
            telegram_id=730014,
            telegram_user_id=730014,
            username="manual_rebind_wrong_slot",
        )
        session.add_all([city, recruiter, candidate, another_candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        await session.refresh(candidate)
        await session.refresh(another_candidate)

        occupied_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=another_candidate.candidate_id,
            candidate_tg_id=another_candidate.telegram_id,
            candidate_fio=another_candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        own_slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=2),
            duration_min=60,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
            candidate_id=candidate.candidate_id,
            candidate_tg_id=candidate.telegram_id,
            candidate_fio=candidate.fio,
            candidate_tz="Europe/Moscow",
            candidate_city_id=city.id,
        )
        session.add_all([occupied_slot, own_slot])
        await session.commit()
        await session.refresh(occupied_slot)
        await session.refresh(own_slot)

        assignment = models.SlotAssignment(
            slot_id=occupied_slot.id,
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

        assignment_id = assignment.id
        occupied_slot_id = occupied_slot.id
        own_slot_id = own_slot.id

    result = await repair_slot_assignment_scheduling_conflict(
        assignment_id=assignment_id,
        repair_action="rebind_assignment_slot",
        chosen_slot_id=own_slot_id,
        confirmations=[
            "selected_slot_is_canonical",
            "rebind_assignment_to_selected_slot",
        ],
        note="rebind to owned slot",
        performed_by_type="admin",
        performed_by_id=0,
    )
    assert result.ok is True
    assert result.status == "repaired"
    assert result.payload["selected_slot_id"] == own_slot_id
    assert result.payload["result_state"]["scheduling_summary"]["slot_id"] == own_slot_id
    assert result.payload["result_state"]["scheduling_summary"]["write_owner"] == "slot_assignment"
    assert result.payload["repairability"] == "not_needed"

    async with async_session() as session:
        assignment = await session.get(models.SlotAssignment, assignment_id)
        occupied_slot = await session.get(models.Slot, occupied_slot_id)
        own_slot = await session.get(models.Slot, own_slot_id)
        audit_log = await session.scalar(
            select(models.AuditLog).where(
                models.AuditLog.action == "scheduling_repair.manual_resolution",
                models.AuditLog.entity_id == str(assignment_id),
            )
        )
        assert assignment is not None
        assert assignment.slot_id == own_slot_id
        assert occupied_slot is not None
        assert occupied_slot.candidate_id == another_candidate.candidate_id
        assert own_slot is not None
        assert own_slot.status == models.SlotStatus.BOOKED
        assert own_slot.candidate_id == candidate.candidate_id
        assert audit_log is not None
        assert audit_log.changes["repair_action"] == "rebind_assignment_slot"
        assert audit_log.changes["selected_slot_id"] == own_slot_id


@pytest.mark.asyncio
async def test_legacy_confirm_slot_by_candidate_syncs_matching_assignment():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        city = models.City(name="Legacy Confirm City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Legacy Confirm Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Legacy Confirm Candidate",
            city="Legacy Confirm City",
            telegram_id=730003,
            telegram_user_id=730003,
            username="legacy_confirm_candidate",
        )
        session.add_all([city, recruiter, candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=30,
            status=models.SlotStatus.BOOKED,
            purpose="interview",
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
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        slot_id = slot.id
        assignment_id = assignment.id

    result = await confirm_slot_by_candidate(slot_id)
    assert result.status == "confirmed"

    async with async_session() as session:
        slot = await session.get(models.Slot, slot_id)
        assignment = await session.get(models.SlotAssignment, assignment_id)
        assert slot is not None
        assert slot.status == models.SlotStatus.CONFIRMED_BY_CANDIDATE
        assert assignment is not None
        assert assignment.status == models.SlotAssignmentStatus.CONFIRMED
        assert assignment.confirmed_at is not None


async def test_repeated_candidate_confirm_syncs_legacy_confirmed_slot_assignment():
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        city = models.City(name="Repeated Confirm City", tz="Europe/Moscow", active=True)
        recruiter = models.Recruiter(name="Repeated Confirm Recruiter", tz="Europe/Moscow", active=True)
        candidate = User(
            fio="Repeated Confirm Candidate",
            city="Repeated Confirm City",
            telegram_id=730004,
            telegram_user_id=730004,
            username="repeated_confirm_candidate",
        )
        session.add_all([city, recruiter, candidate])
        await session.commit()
        await session.refresh(city)
        await session.refresh(recruiter)
        await session.refresh(candidate)

        slot = models.Slot(
            recruiter_id=recruiter.id,
            city_id=city.id,
            tz_name=city.tz,
            start_utc=now + timedelta(days=1),
            duration_min=30,
            status=models.SlotStatus.CONFIRMED_BY_CANDIDATE,
            purpose="interview",
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
            status=models.SlotAssignmentStatus.OFFERED,
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(assignment)

        slot_id = slot.id
        assignment_id = assignment.id

    result = await confirm_slot_by_candidate(slot_id)
    assert result.status == "already_confirmed"

    async with async_session() as session:
        assignment = await session.get(models.SlotAssignment, assignment_id)
        assert assignment is not None
        assert assignment.status == models.SlotAssignmentStatus.CONFIRMED
        assert assignment.confirmed_at is not None
