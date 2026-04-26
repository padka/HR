from __future__ import annotations

import asyncio
import importlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

async_session = None
candidate_services = None
max_recovery_module = None


@pytest.fixture(autouse=True)
def configure_backend(tmp_path):
    global async_session, candidate_services, max_recovery_module

    mp = pytest.MonkeyPatch()
    db_dir = tmp_path / "data_local"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "bot.db"
    mp.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    mp.setenv("DATA_DIR", str(db_dir))
    mp.setenv("LOG_FILE", "data/logs/test_app.log")
    mp.setenv("ENVIRONMENT", "test")
    mp.delenv("SQL_ECHO", raising=False)

    from backend.core import settings as settings_module

    settings_module.get_settings.cache_clear()

    db_module = importlib.import_module("backend.core.db")
    db_module = importlib.reload(db_module)
    candidate_services = importlib.import_module("backend.domain.candidates.services")
    candidate_services = importlib.reload(candidate_services)
    max_recovery_module = importlib.import_module("backend.core.messenger.max_recovery")
    max_recovery_module = importlib.reload(max_recovery_module)
    async_session = db_module.async_session

    from backend.domain.base import Base

    Base.metadata.create_all(bind=db_module.sync_engine)

    yield

    loop = asyncio.new_event_loop()
    loop.run_until_complete(db_module.async_engine.dispose())
    loop.close()
    db_module.sync_engine.dispose()
    settings_module.get_settings.cache_clear()
    mp.undo()


async def _create_candidate(*, max_user_id: str | None = "max-user-1"):
    return await candidate_services.create_or_update_user(
        telegram_id=99001,
        fio="MAX Recovery Candidate",
        city="Москва",
        username="max_recovery_candidate",
        candidate_id="candidate-max-recovery",
        source="max",
    )


async def _bind_candidate_max_user(candidate_id: int, max_user_id: str | None) -> None:
    from backend.domain.candidates.models import User

    async with async_session() as session:
        candidate = await session.get(User, candidate_id)
        assert candidate is not None
        candidate.max_user_id = max_user_id
        candidate.messenger_platform = "max" if max_user_id else "web"
        await session.commit()


async def _create_message(
    *,
    candidate_id: int,
    status: str,
    channel: str = "max",
    direction: str = "outbound",
    delivery_attempts: int = 0,
    delivery_locked_at: datetime | None = None,
    delivery_next_retry_at: datetime | None = None,
    delivery_dead_at: datetime | None = None,
    payload_json: dict | None = None,
    text: str = "Привет из recovery",
) -> int:
    from backend.domain.candidates.models import ChatMessage

    async with async_session() as session:
        message = ChatMessage(
            candidate_id=candidate_id,
            direction=direction,
            channel=channel,
            text=text,
            payload_json=payload_json or {"correlation_id": "corr-1"},
            status=status,
            client_request_id=f"req-{candidate_id}-{status}-{datetime.now(UTC).timestamp()}",
            delivery_attempts=delivery_attempts,
            delivery_locked_at=delivery_locked_at,
            delivery_next_retry_at=delivery_next_retry_at,
            delivery_last_attempt_at=None,
            delivery_dead_at=delivery_dead_at,
            created_at=datetime.now(UTC),
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return int(message.id)


async def _load_message(message_id: int):
    from backend.domain.candidates.models import ChatMessage

    async with async_session() as session:
        return await session.get(ChatMessage, message_id)


class _SuccessfulAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_message(self, chat_id, text: str, *, buttons=None, correlation_id=None):
        self.calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "buttons": buttons,
                "correlation_id": correlation_id,
            }
        )
        return SimpleNamespace(success=True, message_id="mid-1", error=None)


class _FailingAdapter(_SuccessfulAdapter):
    async def send_message(self, chat_id, text: str, *, buttons=None, correlation_id=None):
        self.calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "buttons": buttons,
                "correlation_id": correlation_id,
            }
        )
        return SimpleNamespace(success=False, message_id=None, error="provider_down")


def _settings(**overrides):
    defaults = {
        "max_delivery_recovery_poll_interval": 5.0,
        "max_delivery_recovery_batch_size": 25,
        "max_delivery_recovery_lock_timeout_seconds": 60,
        "max_delivery_recovery_max_attempts": 5,
        "max_delivery_recovery_retry_base_seconds": 30,
        "max_delivery_recovery_retry_max_seconds": 900,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_claim_recoverable_max_messages_filters_due_and_stale_locked_rows() -> None:
    candidate = await _create_candidate()
    await _bind_candidate_max_user(int(candidate.id), "max-user-claim")
    now = datetime.now(UTC)

    due_id = await _create_message(
        candidate_id=int(candidate.id),
        status="failed",
        delivery_attempts=1,
        delivery_next_retry_at=now - timedelta(minutes=5),
        delivery_locked_at=None,
    )
    stale_locked_id = await _create_message(
        candidate_id=int(candidate.id),
        status="queued",
        delivery_attempts=0,
        delivery_next_retry_at=None,
        delivery_locked_at=now - timedelta(minutes=5),
    )
    await _create_message(
        candidate_id=int(candidate.id),
        status="queued",
        delivery_attempts=0,
        delivery_next_retry_at=None,
        delivery_locked_at=now,
    )
    await _create_message(
        candidate_id=int(candidate.id),
        status="failed",
        channel="telegram",
        delivery_attempts=1,
        delivery_next_retry_at=now - timedelta(minutes=5),
    )
    await _create_message(
        candidate_id=int(candidate.id),
        status="dead",
        delivery_attempts=5,
        delivery_dead_at=now,
    )

    claimed = await candidate_services.claim_recoverable_max_messages(
        batch_size=10,
        lock_timeout=timedelta(seconds=60),
    )

    assert {item.id for item in claimed} == {due_id, stale_locked_id}


@pytest.mark.asyncio
async def test_recovery_worker_marks_message_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = await _create_candidate()
    await _bind_candidate_max_user(int(candidate.id), "max-user-success")
    message_id = await _create_message(
        candidate_id=int(candidate.id),
        status="queued",
        delivery_locked_at=datetime.now(UTC) - timedelta(minutes=5),
        payload_json={"correlation_id": "corr-success"},
    )

    adapter = _SuccessfulAdapter()
    async def _fake_ensure_max_adapter(*, settings=None):
        del settings
        return adapter

    monkeypatch.setattr(max_recovery_module, "ensure_max_adapter", _fake_ensure_max_adapter)

    worker = max_recovery_module.MaxDeliveryRecoveryWorker(settings=_settings())
    processed = await worker.run_once()

    message = await _load_message(message_id)
    assert processed == 1
    assert message is not None
    assert message.status == "sent"
    assert message.delivery_attempts == 1
    assert message.delivery_next_retry_at is None
    assert message.delivery_locked_at is None
    assert (message.payload_json or {}).get("provider_message_id") == "mid-1"


@pytest.mark.asyncio
async def test_recovery_worker_does_not_resend_when_provider_boundary_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = await _create_candidate()
    await _bind_candidate_max_user(int(candidate.id), "max-user-boundary")
    message_id = await _create_message(
        candidate_id=int(candidate.id),
        status="failed",
        delivery_attempts=2,
        delivery_next_retry_at=datetime.now(UTC) - timedelta(minutes=5),
        payload_json={"provider_message_id": "mid-already-accepted"},
    )

    adapter = _SuccessfulAdapter()

    async def _fake_ensure_max_adapter(*, settings=None):
        del settings
        return adapter

    monkeypatch.setattr(max_recovery_module, "ensure_max_adapter", _fake_ensure_max_adapter)

    worker = max_recovery_module.MaxDeliveryRecoveryWorker(settings=_settings())
    processed = await worker.run_once()

    message = await _load_message(message_id)
    assert processed == 1
    assert adapter.calls == []
    assert message is not None
    assert message.status == "sent"
    assert message.delivery_attempts == 2
    assert (message.payload_json or {}).get("provider_message_id") == "mid-already-accepted"


@pytest.mark.asyncio
async def test_recovery_worker_schedules_retry_on_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = await _create_candidate()
    await _bind_candidate_max_user(int(candidate.id), "max-user-failure")
    message_id = await _create_message(
        candidate_id=int(candidate.id),
        status="queued",
        delivery_locked_at=datetime.now(UTC) - timedelta(minutes=5),
    )

    adapter = _FailingAdapter()
    async def _fake_ensure_max_adapter(*, settings=None):
        del settings
        return adapter

    monkeypatch.setattr(max_recovery_module, "ensure_max_adapter", _fake_ensure_max_adapter)

    worker = max_recovery_module.MaxDeliveryRecoveryWorker(settings=_settings())
    processed = await worker.run_once()

    message = await _load_message(message_id)
    assert processed == 1
    assert message is not None
    assert message.status == "failed"
    assert message.delivery_attempts == 1
    assert message.delivery_locked_at is None
    assert message.delivery_next_retry_at is not None
    assert message.error == "provider_down"


@pytest.mark.asyncio
async def test_recovery_worker_marks_dead_after_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = await _create_candidate()
    await _bind_candidate_max_user(int(candidate.id), "max-user-dead")
    message_id = await _create_message(
        candidate_id=int(candidate.id),
        status="failed",
        delivery_attempts=4,
        delivery_next_retry_at=datetime.now(UTC) - timedelta(minutes=5),
        delivery_locked_at=None,
    )

    adapter = _FailingAdapter()
    async def _fake_ensure_max_adapter(*, settings=None):
        del settings
        return adapter

    monkeypatch.setattr(max_recovery_module, "ensure_max_adapter", _fake_ensure_max_adapter)

    worker = max_recovery_module.MaxDeliveryRecoveryWorker(
        settings=_settings(max_delivery_recovery_max_attempts=5)
    )
    processed = await worker.run_once()

    message = await _load_message(message_id)
    assert processed == 1
    assert message is not None
    assert message.status == "dead"
    assert message.delivery_attempts == 5
    assert message.delivery_dead_at is not None
    assert message.delivery_next_retry_at is None


@pytest.mark.asyncio
async def test_recovery_worker_treats_missing_adapter_as_retryable_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = await _create_candidate()
    await _bind_candidate_max_user(int(candidate.id), "max-user-no-adapter")
    message_id = await _create_message(
        candidate_id=int(candidate.id),
        status="queued",
        delivery_locked_at=datetime.now(UTC) - timedelta(minutes=5),
    )

    async def _missing_adapter(*, settings=None):
        return None

    monkeypatch.setattr(max_recovery_module, "ensure_max_adapter", _missing_adapter)

    worker = max_recovery_module.MaxDeliveryRecoveryWorker(settings=_settings())
    processed = await worker.run_once()

    message = await _load_message(message_id)
    assert processed == 1
    assert message is not None
    assert message.status == "failed"
    assert message.error == "adapter_unavailable"
    assert message.delivery_attempts == 1
    assert message.delivery_next_retry_at is not None
