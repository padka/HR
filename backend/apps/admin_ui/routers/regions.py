from fastapi import APIRouter, HTTPException

from backend.apps.admin_ui.utils import validate_timezone_name
from backend.core.db import async_session
from backend.domain.models import City

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("/{region_id}/timezone")
async def region_timezone(region_id: int):
    async with async_session() as session:
        city = await session.get(City, region_id)
        if city is None:
            raise HTTPException(status_code=404, detail="Region not found")
        try:
            tz_name = validate_timezone_name(city.tz)
        except ValueError:
            raise HTTPException(status_code=422, detail="Region timezone is invalid")
    return {"timezone": tz_name}
