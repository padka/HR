import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.apps.admin_ui.security import Principal
from backend.core.guards import ensure_candidate_scope, ensure_slot_scope
from backend.core.scoping import scope_candidates, scope_slots, scope_cities
from backend.domain.candidates.models import User
from backend.domain.models import Slot, City


def _extract_values(where_clause):
    values = []
    for cond in where_clause:
        right = getattr(cond, "right", None)
        value = getattr(right, "value", None)
        values.append(value)
    return values


def test_scope_candidates_filters_by_recruiter():
    principal = Principal(type="recruiter", id=7)
    stmt = scope_candidates(select(User), principal)
    values = _extract_values(stmt._where_criteria)
    assert 7 in values


def test_scope_slots_filters_by_recruiter():
    principal = Principal(type="recruiter", id=3)
    stmt = scope_slots(select(Slot), principal)
    values = _extract_values(stmt._where_criteria)
    assert 3 in values


def test_scope_cities_filters_by_recruiter_m2m():
    principal = Principal(type="recruiter", id=5)
    stmt = scope_cities(select(City), principal)
    # join condition carries recruiter_id parameter
    values = _extract_values(stmt._where_criteria)
    assert 5 in values


def test_ensure_candidate_scope_blocks_foreign_candidate():
    principal = Principal(type="recruiter", id=10)
    foreign_user = type("U", (), {"responsible_recruiter_id": 11})()
    with pytest.raises(HTTPException):
        ensure_candidate_scope(foreign_user, principal)


def test_ensure_slot_scope_allows_owner_and_admin():
    rec = Principal(type="recruiter", id=2)
    admin = Principal(type="admin", id=0)
    owned_slot = type("S", (), {"recruiter_id": 2})()
    ensure_slot_scope(owned_slot, rec)  # should not raise
    ensure_slot_scope(owned_slot, admin)  # admin bypass
