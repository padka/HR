# FastAPI Dependency Injection Guide

## Overview

FastAPI Dependency Injection (DI) provides `AsyncSession` and `UnitOfWork` instances per request with automatic cleanup and transaction management.

---

## Benefits

✅ **Automatic Lifecycle Management**
- Session created per request
- Automatic rollback on exceptions
- Automatic cleanup after request

✅ **Better Testing**
- Easy to override dependencies in tests
- Mock UnitOfWork for unit tests
- No global state

✅ **Cleaner Code**
- No manual session management
- Explicit dependencies in function signatures
- Type hints for better IDE support

✅ **Transaction Safety**
- One session per request
- Explicit commit required (no auto-commit)
- Rollback on any exception

---

## Usage

### 1. Inject AsyncSession

For simple database queries:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.dependencies import get_async_session
from backend.domain.models import Recruiter

router = APIRouter()

@router.get("/recruiters")
async def list_recruiters(
    session: AsyncSession = Depends(get_async_session)
):
    """List recruiters using injected session."""
    result = await session.execute(
        select(Recruiter).where(Recruiter.active == True)
    )
    recruiters = result.scalars().all()
    return {"recruiters": [r.name for r in recruiters]}
```

### 2. Inject UnitOfWork (Recommended)

For operations using repositories:

```python
from fastapi import APIRouter, Depends
from backend.core.dependencies import get_uow
from backend.core.uow import UnitOfWork

router = APIRouter()

@router.get("/recruiters/{id}")
async def get_recruiter(
    id: int,
    uow: UnitOfWork = Depends(get_uow)
):
    """Get recruiter using UnitOfWork."""
    result = await uow.recruiters.get(id)

    match result:
        case Success(recruiter):
            return {"recruiter": recruiter}
        case Failure(NotFoundError()):
            raise HTTPException(404, "Recruiter not found")
        case Failure(error):
            raise HTTPException(500, str(error))


@router.post("/recruiters")
async def create_recruiter(
    data: RecruiterCreate,
    uow: UnitOfWork = Depends(get_uow)
):
    """Create recruiter with automatic transaction management."""
    recruiter = Recruiter(name=data.name, active=True)

    result = await uow.recruiters.add(recruiter)

    if result.is_failure():
        raise HTTPException(400, str(result.error))

    # Explicit commit required
    await uow.commit()

    return {"id": recruiter.id, "name": recruiter.name}
```

### 3. Multiple Repository Operations

```python
@router.post("/slots")
async def create_slot(
    data: SlotCreate,
    uow: UnitOfWork = Depends(get_uow)
):
    """Create slot with recruiter and city validation."""
    # All operations use the same session/transaction
    recruiter_result = await uow.recruiters.get(data.recruiter_id)
    city_result = await uow.cities.get(data.city_id)

    if recruiter_result.is_failure() or city_result.is_failure():
        raise HTTPException(404, "Recruiter or city not found")

    slot = Slot(
        recruiter_id=data.recruiter_id,
        city_id=data.city_id,
        start_utc=data.start_utc,
        end_utc=data.end_utc,
    )

    result = await uow.slots.add(slot)

    if result.is_failure():
        raise HTTPException(400, str(result.error))

    # Commit all changes atomically
    await uow.commit()

    return {"id": slot.id}
```

---

## Migration Guide

### From Manual Session to DI

**Before (Manual Session):**
```python
async def list_slots(recruiter_id: Optional[int]) -> List[Slot]:
    async with async_session() as session:
        query = select(Slot)
        if recruiter_id:
            query = query.where(Slot.recruiter_id == recruiter_id)
        result = await session.execute(query)
        return result.scalars().all()
```

**After (Dependency Injection):**
```python
async def list_slots(
    recruiter_id: Optional[int],
    session: AsyncSession = Depends(get_async_session)
) -> List[Slot]:
    query = select(Slot)
    if recruiter_id:
        query = query.where(Slot.recruiter_id == recruiter_id)
    result = await session.execute(query)
    return result.scalars().all()
```

### From Manual UoW to DI

**Before (Manual UoW):**
```python
async def create_recruiter(data: RecruiterCreate):
    async with UnitOfWork() as uow:
        recruiter = Recruiter(name=data.name)
        result = await uow.recruiters.add(recruiter)
        if result.is_success():
            await uow.commit()
            return result.unwrap()
        raise ValueError("Failed to create")
```

**After (Dependency Injection):**
```python
async def create_recruiter(
    data: RecruiterCreate,
    uow: UnitOfWork = Depends(get_uow)
):
    recruiter = Recruiter(name=data.name)
    result = await uow.recruiters.add(recruiter)

    if result.is_failure():
        raise HTTPException(400, str(result.error))

    await uow.commit()
    return result.unwrap()
```

---

## Service Layer Pattern

For complex business logic, use service classes with DI:

```python
# services/recruiter_service.py
from backend.core.uow import UnitOfWork

class RecruiterService:
    """Business logic for recruiter operations."""

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def activate_recruiter(self, recruiter_id: int) -> bool:
        """Activate recruiter and sync with external systems."""
        result = await self.uow.recruiters.get(recruiter_id)

        if result.is_failure():
            return False

        recruiter = result.unwrap()
        recruiter.active = True

        await self.uow.recruiters.update(recruiter)
        await self.uow.commit()

        # Trigger other operations...
        return True


# routers/recruiters.py
@router.post("/recruiters/{id}/activate")
async def activate_recruiter(
    id: int,
    uow: UnitOfWork = Depends(get_uow)
):
    """Activate recruiter endpoint."""
    service = RecruiterService(uow)
    success = await service.activate_recruiter(id)

    if not success:
        raise HTTPException(404, "Recruiter not found")

    return {"success": True}
```

---

## Testing with DI

### Override Dependencies in Tests

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from backend.core.dependencies import get_uow
from backend.core.result import Success

def test_create_recruiter():
    # Create mock UoW
    mock_uow = AsyncMock()
    mock_uow.recruiters.add = AsyncMock(
        return_value=Success(Recruiter(id=1, name="Test"))
    )
    mock_uow.commit = AsyncMock()

    # Override dependency
    app.dependency_overrides[get_uow] = lambda: mock_uow

    # Test endpoint
    client = TestClient(app)
    response = client.post("/recruiters", json={"name": "Test"})

    assert response.status_code == 200
    mock_uow.commit.assert_called_once()
```

---

## Best Practices

### DO ✅

1. **Use UnitOfWork for repository operations**
   ```python
   uow: UnitOfWork = Depends(get_uow)
   ```

2. **Always commit explicitly**
   ```python
   await uow.commit()
   ```

3. **Handle Result types with pattern matching**
   ```python
   match result:
       case Success(value): ...
       case Failure(error): ...
   ```

4. **Use type hints for dependencies**
   ```python
   async def handler(uow: UnitOfWork = Depends(get_uow)):
   ```

### DON'T ❌

1. **Don't create sessions manually in endpoints**
   ```python
   # ❌ Bad
   async with async_session() as session:
       ...
   ```

2. **Don't forget to commit**
   ```python
   # ❌ Bad - changes not saved
   await uow.items.add(item)
   # Missing: await uow.commit()
   ```

3. **Don't mix manual and DI sessions**
   ```python
   # ❌ Bad - different sessions
   async def handler(uow: UnitOfWork = Depends(get_uow)):
       async with async_session() as session:  # Different session!
           ...
   ```

---

## Gradual Migration Strategy

1. **Phase 1: New Endpoints**
   - Use DI for all new endpoints
   - Establish pattern for team

2. **Phase 2: High-Traffic Endpoints**
   - Migrate most-used endpoints first
   - Measure performance improvements

3. **Phase 3: Complete Migration**
   - Migrate remaining endpoints
   - Remove manual session creation

4. **Phase 4: Deprecate Old Pattern**
   - Mark manual session functions as deprecated
   - Update documentation

---

## Performance Considerations

### Connection Pooling

FastAPI DI works seamlessly with connection pooling:

```python
# backend/core/db.py (already configured)
async_engine = create_async_engine(
    database_url,
    pool_size=20,        # Max connections in pool
    max_overflow=10,     # Additional connections allowed
    pool_pre_ping=True,  # Verify connections before use
)
```

### Session Lifecycle

```
Request → Create Session → Use in Endpoint → Commit/Rollback → Close Session → Response
           ↑                                    ↑                 ↑
           DI creates                           Service logic     DI cleanup
```

---

## Troubleshooting

### "Session is closed"

**Cause:** Trying to access session after request completes

**Solution:** Don't store session/UoW references outside request scope

```python
# ❌ Bad
session_cache = None

@router.get("/items")
async def handler(session: AsyncSession = Depends(get_async_session)):
    global session_cache
    session_cache = session  # Don't do this!

# ✅ Good
@router.get("/items")
async def handler(session: AsyncSession = Depends(get_async_session)):
    # Use session only within request
    result = await session.execute(...)
    return result
```

### "RuntimeError: UnitOfWork not initialized"

**Cause:** Trying to use UoW outside context manager

**Solution:** Let FastAPI DI manage the context

```python
# ❌ Bad
uow = UnitOfWork()
await uow.items.get(1)  # Error!

# ✅ Good
async def handler(uow: UnitOfWork = Depends(get_uow)):
    # DI handles context manager
    await uow.items.get(1)  # Works!
```

---

## See Also

- [Phase 1: Architecture Guide](ARCHITECTURE_GUIDE.md)
- [Phase 2: Performance](PHASE2_PERFORMANCE.md)
- [UnitOfWork Pattern](../backend/core/uow.py)
- [Result Pattern](../backend/core/result.py)
