import asyncio

import pytest
import pytest_asyncio

from backend.apps.bot.broker import NotificationBroker

pytestmark = [pytest.mark.asyncio, pytest.mark.notifications]

try:  # pragma: no cover - redis optional
    import redis.asyncio as redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore


@pytest_asyncio.fixture
async def redis_client(redis_url):
    if redis is None:
        pytest.skip("redis-py not installed")
    client = redis.Redis.from_url(redis_url)
    try:
        await client.ping()
    except Exception:
        await client.aclose()
        pytest.skip(f"redis service is not running at {redis_url}")
    await client.flushdb()
    yield client
    try:
        await client.aclose()
    except Exception:
        pass  # Ignore close errors


@pytest_asyncio.fixture
async def broker(redis_client):
    broker = NotificationBroker(redis_client, stream_key="test:notifications", dlq_key="test:notifications:dlq")
    await broker.start()
    yield broker
    await redis_client.delete("test:notifications")
    await redis_client.delete("test:notifications:dlq")


async def drain(broker):
    return await broker.read(count=10, block_ms=10)


@pytest.mark.integration
async def test_enqueue_dequeue_and_acknowledge(broker):
    payload = {"type": "test", "candidate_id": 42}
    message_id = await broker.publish(payload)
    assert message_id

    messages = await broker.read(count=1, block_ms=50)
    assert len(messages) == 1
    # Redis stores everything as strings, so convert for comparison
    assert int(messages[0].payload["candidate_id"]) == 42

    await broker.ack(messages[0].id)
    assert await drain(broker) == []


@pytest.mark.integration
async def test_requeue_increments_not_before(broker):
    await broker.publish({"type": "retry", "candidate_id": 1})
    messages = await broker.read(count=1, block_ms=50)
    message = messages[0]
    not_before = message.payload["not_before"]

    await broker.requeue(message, delay_seconds=1)
    messages = await broker.read(count=1, block_ms=50)
    message = messages[0]
    assert message.payload["not_before"] >= not_before


@pytest.mark.integration
async def test_dlq_receives_failed_message(broker, redis_client):
    await broker.publish({"type": "fail"})
    message = (await broker.read(count=1, block_ms=50))[0]
    await broker.to_dlq(message, reason="max_attempts")

    dlq_entries = await redis_client.xrange("test:notifications:dlq", count=1)
    assert dlq_entries


@pytest.mark.integration
async def test_claim_stale_reclaims_messages(broker):
    await broker.publish({"type": "stale"})
    message = (await broker.read(count=1, block_ms=50))[0]
    # Do not ack, let it become idle
    await asyncio.sleep(0.1)
    reclaimed = await broker.claim_stale(min_idle_ms=1, count=1)
    assert len(reclaimed) == 1
    assert reclaimed[0].payload["type"] == "stale"
