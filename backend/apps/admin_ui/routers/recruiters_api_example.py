"""
Example API router demonstrating FastAPI Dependency Injection.

This module shows how to use DI for AsyncSession and UnitOfWork in endpoints.
It serves as a reference implementation for migrating existing code.

NOT YET INTEGRATED - This is a reference example for migration.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import get_async_session, get_uow
from backend.core.result import Failure, NotFoundError, Success
from backend.core.uow import UnitOfWork
from backend.domain.models import Recruiter

router = APIRouter(prefix="/api/v2/recruiters", tags=["Recruiters API v2"])


# --- DTOs ---


class RecruiterResponse(BaseModel):
    id: int
    name: str
    active: bool
    tz: str

    class Config:
        from_attributes = True


class RecruiterCreate(BaseModel):
    name: str
    tz: str = "Europe/Moscow"
    active: bool = True


class RecruiterUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    tz: Optional[str] = None


# --- Endpoints using AsyncSession DI ---


@router.get("/simple", response_model=List[RecruiterResponse])
async def list_recruiters_simple(
    active_only: bool = True,
    session: AsyncSession = Depends(get_async_session),
):
    """
    List recruiters using injected AsyncSession.

    Demonstrates:
    - AsyncSession dependency injection
    - Simple query without repositories
    - Automatic session cleanup
    """
    query = select(Recruiter).order_by(Recruiter.name.asc())

    if active_only:
        query = query.where(Recruiter.active == True)  # noqa: E712

    result = await session.execute(query)
    recruiters = result.scalars().all()

    return [RecruiterResponse.from_orm(r) for r in recruiters]


# --- Endpoints using UnitOfWork DI (Recommended) ---


@router.get("", response_model=List[RecruiterResponse])
async def list_recruiters(
    active_only: bool = True,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    List recruiters using UnitOfWork (recommended approach).

    Demonstrates:
    - UnitOfWork dependency injection
    - Repository pattern usage
    - Result type handling
    - Phase 2 caching (get_active is cached)
    """
    if active_only:
        result = await uow.recruiters.get_active()
    else:
        result = await uow.recruiters.get_all()

    match result:
        case Success(recruiters):
            return [RecruiterResponse.from_orm(r) for r in recruiters]
        case Failure(error):
            raise HTTPException(500, f"Failed to fetch recruiters: {error}")


@router.get("/{recruiter_id}", response_model=RecruiterResponse)
async def get_recruiter(
    recruiter_id: int,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Get single recruiter by ID.

    Demonstrates:
    - UnitOfWork dependency injection
    - Result pattern matching
    - Proper error handling
    - Phase 2 caching (get is cached with LONG TTL)
    """
    result = await uow.recruiters.get(recruiter_id)

    match result:
        case Success(recruiter):
            return RecruiterResponse.from_orm(recruiter)
        case Failure(NotFoundError()):
            raise HTTPException(404, f"Recruiter {recruiter_id} not found")
        case Failure(error):
            raise HTTPException(500, str(error))


@router.post("", response_model=RecruiterResponse, status_code=201)
async def create_recruiter(
    data: RecruiterCreate,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Create new recruiter.

    Demonstrates:
    - UnitOfWork dependency injection
    - Entity creation
    - Explicit commit
    - Phase 2 cache invalidation (add invalidates recruiters:*)
    """
    recruiter = Recruiter(
        name=data.name,
        tz=data.tz,
        active=data.active,
    )

    result = await uow.recruiters.add(recruiter)

    match result:
        case Success(created):
            # Explicit commit required
            await uow.commit()
            return RecruiterResponse.from_orm(created)
        case Failure(error):
            raise HTTPException(400, f"Failed to create recruiter: {error}")


@router.patch("/{recruiter_id}", response_model=RecruiterResponse)
async def update_recruiter(
    recruiter_id: int,
    data: RecruiterUpdate,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Update recruiter.

    Demonstrates:
    - UnitOfWork dependency injection
    - Entity update
    - Partial updates with Pydantic
    - Transaction management
    - Phase 2 cache invalidation (update invalidates recruiters:* and recruiter:id)
    """
    # Get existing recruiter
    get_result = await uow.recruiters.get(recruiter_id)

    match get_result:
        case Failure(NotFoundError()):
            raise HTTPException(404, f"Recruiter {recruiter_id} not found")
        case Failure(error):
            raise HTTPException(500, str(error))
        case Success(recruiter):
            # Apply updates
            if data.name is not None:
                recruiter.name = data.name
            if data.active is not None:
                recruiter.active = data.active
            if data.tz is not None:
                recruiter.tz = data.tz

            # Update in repository
            update_result = await uow.recruiters.update(recruiter)

            match update_result:
                case Success(updated):
                    await uow.commit()
                    return RecruiterResponse.from_orm(updated)
                case Failure(error):
                    raise HTTPException(400, f"Failed to update: {error}")


@router.delete("/{recruiter_id}", status_code=204)
async def delete_recruiter(
    recruiter_id: int,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Delete recruiter.

    Demonstrates:
    - UnitOfWork dependency injection
    - Entity deletion
    - 204 No Content response
    - Phase 2 cache invalidation (delete invalidates recruiters:* and recruiter:id)
    """
    result = await uow.recruiters.delete(recruiter_id)

    match result:
        case Success(deleted):
            if not deleted:
                raise HTTPException(404, f"Recruiter {recruiter_id} not found")
            await uow.commit()
            return None  # 204 No Content
        case Failure(error):
            raise HTTPException(500, str(error))


# --- Complex example with multiple repositories ---


@router.get("/{recruiter_id}/cities", response_model=List[str])
async def get_recruiter_cities(
    recruiter_id: int,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Get cities linked to a recruiter.

    Demonstrates:
    - Multiple repository access in single request
    - Using same UnitOfWork for all operations
    - Relationship navigation
    """
    result = await uow.recruiters.get(recruiter_id)

    match result:
        case Success(recruiter):
            # Access relationship (may trigger query if not eager loaded)
            return [city.name for city in recruiter.cities]
        case Failure(NotFoundError()):
            raise HTTPException(404, f"Recruiter {recruiter_id} not found")
        case Failure(error):
            raise HTTPException(500, str(error))


@router.get("/{recruiter_id}/slots/free", response_model=int)
async def count_free_slots(
    recruiter_id: int,
    uow: UnitOfWork = Depends(get_uow),
):
    """
    Count free slots for recruiter.

    Demonstrates:
    - Using multiple repositories
    - Cross-repository queries
    - Combining repository methods
    """
    from datetime import datetime, timezone

    # Verify recruiter exists
    recruiter_result = await uow.recruiters.exists(recruiter_id)

    match recruiter_result:
        case Success(exists):
            if not exists:
                raise HTTPException(404, f"Recruiter {recruiter_id} not found")
        case Failure(error):
            raise HTTPException(500, str(error))

    # Get free slots
    slots_result = await uow.slots.get_free_for_recruiter(
        recruiter_id=recruiter_id,
        after=datetime.now(timezone.utc),
    )

    match slots_result:
        case Success(slots):
            return len(slots)
        case Failure(error):
            raise HTTPException(500, str(error))
