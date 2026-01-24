from __future__ import annotations

from sqlalchemy import Select, exists, select
from sqlalchemy.orm import aliased

from backend.domain.models import City, Slot, recruiter_city_association
from backend.domain.candidates.models import User
from backend.apps.admin_ui.security import Principal


def scope_candidates(stmt: Select, principal: Principal) -> Select:
    if principal.type == "admin":
        return stmt
    return stmt.where(User.responsible_recruiter_id == principal.id)


def scope_slots(stmt: Select, principal: Principal) -> Select:
    if principal.type == "admin":
        return stmt
    return stmt.where(Slot.recruiter_id == principal.id)


def scope_cities(stmt: Select, principal: Principal) -> Select:
    if principal.type == "admin":
        return stmt
    # city visible if recruiter linked via recruiter_cities
    assoc = recruiter_city_association
    return (
        stmt.join(assoc, assoc.c.city_id == City.id)
        .where(assoc.c.recruiter_id == principal.id)
    )
