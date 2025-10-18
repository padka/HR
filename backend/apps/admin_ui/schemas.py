from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class RecruiterOption(BaseModel):
    """Public data about recruiters safe for UI templates."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tz: Optional[str] = None
    active: Optional[bool] = None


class CityOption(BaseModel):
    """Public data about cities safe for UI templates."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tz: Optional[str] = None
    active: Optional[bool] = None
    responsible_recruiter_id: Optional[int] = None
