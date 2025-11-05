# Batch Notification Processing Architecture

## Recommended Architecture (Not Yet Implemented)

### Current Issues
- Multiple SELECT queries in hot loop
- Separate UoW per notification (N transactions)
- Inefficient claim → process → commit pattern

### Recommended Changes

```python
# Recommended pattern (pseudo-code):
async def process_notifications_batch(batch_size: int = 100):
    """Process notifications in batches with single UoW per cycle."""
    async with UnitOfWork() as uow:
        # 1. Claim batch of outbox items in ONE query
        outbox_items = await uow.outbox.claim_pending(limit=batch_size)

        if not outbox_items:
            return

        # 2. Process each item (send to Telegram)
        results = []
        for item in outbox_items:
            success = await send_telegram_message(item)
            results.append((item.id, success))

        # 3. Update all statuses in ONE commit
        for item_id, success in results:
            if success:
                await uow.outbox.mark_delivered(item_id)
            else:
                await uow.outbox.mark_failed(item_id)

        # 4. Single commit for entire batch
        await uow.commit()
```

### Benefits
- 100x fewer database round-trips
- Single transaction per batch
- Better error handling
- Easier monitoring

---

# Distributed Scheduler Architecture (Task 7)

## Recommended: APScheduler + Redis JobStore

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

# Production configuration
jobstores = {
    'default': RedisJobStore(
        host='localhost',
        port=6379,
        db=1,  # Separate DB for scheduler
    )
}

scheduler = AsyncIOScheduler(jobstores=jobstores)

# Only ONE instance becomes leader
# Other instances are passive followers
```

### Benefits
- Distributed coordination
- No duplicate job execution
- Survives instance restarts
- Multi-instance safe

---

# Object Storage for Bot Files (Task 8)

## Recommended: S3-compatible Storage

```python
# Abstract storage interface
class FileStorage(Protocol):
    async def upload(self, file: bytes, key: str) -> str:
        """Upload file and return URL."""

    async def download(self, key: str) -> bytes:
        """Download file by key."""

    async def delete(self, key: str) -> bool:
        """Delete file."""

# S3 implementation
class S3Storage(FileStorage):
    def __init__(self, bucket: str, endpoint: str):
        self.s3_client = boto3.client('s3', endpoint_url=endpoint)
        self.bucket = bucket

    async def upload(self, file: bytes, key: str) -> str:
        await self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file
        )
        return f"https://{self.bucket}.s3.amazonaws.com/{key}"
```

### Benefits
- Horizontal scaling
- CDN integration
- No local disk dependency
- Better availability

---

## Implementation Status

**Tasks 6-8: NOT IMPLEMENTED**

These are architectural recommendations only. Full implementation requires:
- Significant refactoring of existing code
- Thorough testing
- Gradual migration strategy
- Production validation

**Recommendation:** Implement incrementally in future sprints with proper testing.
