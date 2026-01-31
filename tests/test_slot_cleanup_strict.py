import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.apps.admin_ui.services.slots import delete_past_free_slots
from backend.domain.models import Slot, SlotStatus, Recruiter, SlotAssignment
from backend.domain.candidates.models import User
from backend.core.settings import get_settings
from backend.core.time_utils import ensure_aware_utc

# Use a test-specific session factory to avoid fixture issues in standalone run
@pytest.fixture
async def session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url_async)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as sess:
        yield sess
    await engine.dispose()

@pytest.fixture
async def recruiter(session):
    rec = Recruiter(name="Cleanup Tester", active=True, tz="UTC")
    session.add(rec)
    await session.commit()
    await session.refresh(rec)
    return rec

@pytest.mark.asyncio
async def test_slot_cleanup_logic(session, recruiter):
    # Reference time: fixed "now"
    now = ensure_aware_utc(datetime.now(timezone.utc))
    
    # CASE A: FREE slot, start = now - 2m. Should be DELETED (grace=1).
    slot_a = Slot(
        recruiter_id=recruiter.id,
        start_utc=now - timedelta(minutes=2),
        duration_min=60,
        status=SlotStatus.FREE,
        purpose="interview",
        tz_name="UTC"
    )
    session.add(slot_a)

    # CASE B: FREE slot, start = now - 30s. Should NOT be deleted (grace=1).
    slot_b = Slot(
        recruiter_id=recruiter.id,
        start_utc=now - timedelta(seconds=30),
        duration_min=60,
        status=SlotStatus.FREE,
        purpose="interview",
        tz_name="UTC"
    )
    session.add(slot_b)

    # CASE C: FREE slot, start = now - 1m - 1s. Should be DELETED (grace=1).
    slot_c = Slot(
        recruiter_id=recruiter.id,
        start_utc=now - timedelta(minutes=1, seconds=1),
        duration_min=60,
        status=SlotStatus.FREE,
        purpose="interview",
        tz_name="UTC"
    )
    session.add(slot_c)

    # CASE D: OCCUPIED slot (status=BOOKED), start = now - 10m. Should NOT be deleted.
    slot_d = Slot(
        recruiter_id=recruiter.id,
        start_utc=now - timedelta(minutes=10),
        duration_min=60,
        status=SlotStatus.BOOKED, # Not free
        purpose="interview",
        tz_name="UTC",
        candidate_tg_id=12345 
    )
    session.add(slot_d)

    # CASE D2: OCCUPIED slot (status=FREE but has candidate_id? Should theoretically not happen but test safety).
    # If logic is strict "status=FREE AND candidate is NULL", this slot should NOT be deleted if it has candidate.
    slot_d2 = Slot(
        recruiter_id=recruiter.id,
        start_utc=now - timedelta(minutes=10),
        duration_min=60,
        status=SlotStatus.FREE, 
        purpose="interview",
        tz_name="UTC",
        candidate_tg_id=67890 # Occupied by linkage
    )
    session.add(slot_d2)

    # CASE E: FUTURE FREE slot. Should NOT be deleted.
    slot_e = Slot(
        recruiter_id=recruiter.id,
        start_utc=now + timedelta(minutes=10),
        duration_min=60,
        status=SlotStatus.FREE,
        purpose="interview",
        tz_name="UTC"
    )
    session.add(slot_e)

    await session.commit()

    # --- EXECUTE ---
    # Pass 'now' explicitly to ensure deterministic test
    deleted, total = await delete_past_free_slots(grace_minutes=1, session=session, now_utc=now)

    # --- VERIFY ---
    # Expected deleted: A, C. (2 slots)
    # Expected kept: B (too new), D (booked), D2 (has candidate), E (future).
    
    assert deleted == 2
    
    # Check A deleted
    assert await session.get(Slot, slot_a.id) is None
    # Check C deleted
    assert await session.get(Slot, slot_c.id) is None
    
    # Check B exists
    assert await session.get(Slot, slot_b.id) is not None
    # Check D exists
    assert await session.get(Slot, slot_d.id) is not None
    # Check D2 exists (safety check against accidental deletion of corrupt slots)
    assert await session.get(Slot, slot_d2.id) is not None
    # Check E exists
    assert await session.get(Slot, slot_e.id) is not None
