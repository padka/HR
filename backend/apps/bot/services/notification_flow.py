"""Notification flow services."""

from . import base as _base

for _name in dir(_base):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    globals()[_name] = getattr(_base, _name)

from backend.core.messenger.channel_state import (
    mark_messenger_channel_healthy,
    set_messenger_channel_degraded,
)
from backend.core.messenger.protocol import SendResult
from backend.core.messenger.reliability import classify_delivery_failure
from backend.core.db import async_session
from backend.domain.candidates.models import User
from backend.domain.models import Slot
from sqlalchemy import select


def _uses_legacy_status_update_text(text: str) -> bool:
    rendered = (text or "").strip()
    if not rendered:
        return False
    return (
        rendered.startswith("Ваш статус обновлён:")
        or "{status}" in rendered
        or "{booking_id}" in rendered
    )

class NotificationService:
    """Minimal outbox worker for interview confirmation notifications."""

    def __init__(
        self,
        *,
        scheduler: Optional[AsyncIOScheduler] = None,
        template_provider: Optional[TemplateProvider] = None,
        broker: Optional[NotificationBrokerProtocol] = None,
        poll_interval: float = 3.0,
        batch_size: int = 100,
        rate_limit_per_sec: float = 10.0,
        max_attempts: int = 8,
        retry_base_delay: int = 30,
        retry_max_delay: int = 3600,
        circuit_break_window: tuple[int, int] = (30, 60),
        worker_concurrency: int = 1,
    ) -> None:
        self._scheduler = scheduler
        if template_provider is None:
            self._template_provider = get_template_provider()
        else:
            self._template_provider = template_provider
            global _template_provider
            _template_provider = template_provider
        self._base_poll_interval = max(poll_interval, 0.5)
        self._current_poll_interval = self._base_poll_interval
        self._batch_size = max(1, batch_size)
        self._max_attempts = max(1, max_attempts)
        self._retry_base = max(1, retry_base_delay)
        self._retry_max = max(self._retry_base, retry_max_delay)
        low, high = circuit_break_window
        self._breaker_window = (max(1, low), max(1, high))
        self._breaker_open_until: float = 0.0
        self._token_bucket = (
            _TokenBucket(rate_limit_per_sec, max(1, int(rate_limit_per_sec) * 2))
            if rate_limit_per_sec > 0
            else None
        )
        self._broker = broker
        self._job_id = "notification:outbox_worker"
        self._worker_concurrency = max(1, worker_concurrency)
        self._poll_gate = asyncio.Semaphore(self._worker_concurrency)
        self._task: Optional[asyncio.Task] = None
        self._poll_tasks: set[asyncio.Task] = set()
        self._scheduler_jobs: set[asyncio.Task] = set()
        self._claim_idle_ms = 60000
        self._current_message: Optional[BrokerMessage] = None
        self._skipped_runs: int = 0
        self._started: bool = False
        self._shutting_down: bool = False
        self._loop_enabled: bool = False
        self._watchdog_task: Optional[asyncio.Task] = None
        self._watchdog_interval = max(self._current_poll_interval * 2, 10.0)
        self._watchdog_alert_threshold = max(self._current_poll_interval * 6, 15.0)
        self._last_poll_ts: float = 0.0
        self._idle_backoff_steps = self._build_idle_backoff_steps()
        self._idle_backoff_index = 0
        self._last_idle_log_ts: float = 0.0
        self._idle_log_interval = 60.0
        self._last_db_error_ts: float = 0.0
        self._db_error_log_interval = 300.0
        self._fatal_error_code: Optional[str] = None
        self._fatal_error_at: Optional[datetime] = None
        self._last_delivery_error: Optional[str] = None
        self._use_scheduler_job: bool = True

    async def invalidate_template_cache(
        self,
        *,
        key: Optional[str] = None,
        locale: str = "ru",
        channel: str = "tg",
        city_id: Optional[int] = None,
    ) -> None:
        """Invalidate cached message templates so edits apply without restart.

        Best effort: failures are logged but do not raise, because the caller is
        typically a background pub/sub listener.
        """

        try:
            await self._template_provider.invalidate(
                key=key,
                locale=locale,
                channel=channel,
                city_id=city_id,
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception(
                "notification.template_invalidate_failed",
                extra={
                    "key": key,
                    "locale": locale,
                    "channel": channel,
                    "city_id": city_id,
                },
            )

    def start(self, *, allow_poll_loop: bool = False) -> None:
        self._shutting_down = False
        if self._started:
            return
        # Loop mode is preferred when explicitly allowed: it keeps a continuous
        # broker read (xreadgroup block) running and avoids latency gaps that can
        # happen with interval-based scheduling when a message arrives shortly
        # after a fast poll iteration.
        if allow_poll_loop:
            self._use_scheduler_job = False
            if self._scheduler is not None:
                try:
                    self._scheduler.remove_job(self._job_id)
                except Exception:
                    pass
            self._enable_poll_loop()
            self._started = True
            self._ensure_watchdog()
            return

        scheduler_started = False
        scheduler_failed = False

        if self._scheduler is not None:
            try:
                self._ensure_scheduler_job()
                scheduler_started = True
                self._use_scheduler_job = True
            except Exception:
                scheduler_failed = True
                logger.exception("notification.worker.scheduler_start_failed")

        if scheduler_started:
            self._started = True
            self._ensure_watchdog()
            return

        if scheduler_failed:
            logger.warning("notification.worker.scheduler_fallback_loop")
            self._use_scheduler_job = False
            self._enable_poll_loop()
            self._started = True
            self._ensure_watchdog()
            return

        # No scheduler and loop not allowed: do nothing.
        return

    def _enable_poll_loop(self) -> None:
        if self._shutting_down:
            return
        self._loop_enabled = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("notification.worker.poll_loop_start_failed", extra={"reason": "no_loop"})
            return
        if self._task is None or self._task.done():
            self._task = loop.create_task(self._poll_loop())

    def _ensure_watchdog(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = loop.create_task(self._watchdog_loop())

    def _build_idle_backoff_steps(self) -> list[float]:
        steps = [self._base_poll_interval, 10.0, 30.0, 60.0]
        normalized: list[float] = []
        for step in steps:
            if step < self._base_poll_interval:
                continue
            if step not in normalized:
                normalized.append(step)
        return normalized

    def _apply_poll_interval(self, interval: float, *, reason: str) -> None:
        if interval == self._current_poll_interval:
            return
        self._current_poll_interval = interval
        self._watchdog_interval = max(self._current_poll_interval * 2, 10.0)
        self._watchdog_alert_threshold = max(self._current_poll_interval * 6, 15.0)
        if self._scheduler is not None:
            job = self._scheduler.get_job(self._job_id)
            if job is not None:
                job.reschedule("interval", seconds=self._current_poll_interval)
        logger.info(
            "notification.worker.poll_interval_updated",
            extra={"interval": round(self._current_poll_interval, 2), "reason": reason},
        )

    def _reset_idle_backoff(self) -> None:
        if self._idle_backoff_index != 0:
            self._idle_backoff_index = 0
            self._apply_poll_interval(self._idle_backoff_steps[0], reason="work_found")

    def _advance_idle_backoff(self, reason: str) -> None:
        if self._idle_backoff_index < len(self._idle_backoff_steps) - 1:
            self._idle_backoff_index += 1
        next_interval = self._idle_backoff_steps[self._idle_backoff_index]
        self._apply_poll_interval(next_interval, reason=reason)

    def _record_db_unavailable(self, exc: Exception, *, context: str) -> None:
        now = time.monotonic()
        if now - self._last_db_error_ts < self._db_error_log_interval:
            return
        self._last_db_error_ts = now
        logger.warning(
            "notification.worker.db_unavailable",
            extra={"context": context, "error": str(exc)},
        )

    async def _stop_watchdog(self) -> None:
        if self._watchdog_task is None:
            return
        self._watchdog_task.cancel()
        try:
            await self._watchdog_task
        except asyncio.CancelledError:
            pass
        self._watchdog_task = None

    async def _await_scheduler_jobs(self) -> None:
        if not self._scheduler_jobs:
            return
        await asyncio.gather(*list(self._scheduler_jobs), return_exceptions=True)
        self._scheduler_jobs.clear()

    async def _watchdog_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._watchdog_interval)
                if not self._started or self._shutting_down:
                    return
                if self._scheduler is not None and self._use_scheduler_job:
                    job = self._scheduler.get_job(self._job_id)
                    if job is None:
                        logger.warning("notification.worker.watchdog_job_missing")
                        try:
                            self._ensure_scheduler_job()
                        except Exception:
                            logger.exception("notification.worker.watchdog_job_restart_failed")
                            if not self._loop_enabled:
                                self._enable_poll_loop()
                    elif not self._scheduler.running:
                        try:
                            self._scheduler.start()
                        except SchedulerAlreadyRunningError:
                            pass
                        except Exception:
                            logger.exception("notification.worker.watchdog_scheduler_start_failed")
                elif self._loop_enabled:
                    if self._task is None or self._task.done():
                        logger.warning("notification.worker.watchdog_restart_loop")
                        self._enable_poll_loop()
                seconds_since_poll = None
                if self._last_poll_ts:
                    seconds_since_poll = max(0.0, time.monotonic() - self._last_poll_ts)
                    await record_notification_poll_staleness(seconds_since_poll)
                    if seconds_since_poll > self._watchdog_alert_threshold:
                        logger.warning(
                            "notification.worker.poll_stalled",
                            extra={"seconds_since_poll": round(seconds_since_poll, 2)},
                        )
                else:
                    await record_notification_poll_staleness(0.0)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("notification.worker.watchdog_failed")

    async def shutdown(self) -> None:
        self._shutting_down = True
        self._started = False
        self._loop_enabled = False
        await self._stop_watchdog()
        if self._scheduler is not None:
            try:
                self._scheduler.remove_job(self._job_id)
            except Exception:
                pass
        await self._await_scheduler_jobs()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        for task in list(self._poll_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._poll_tasks.clear()
        if self._broker is not None:
            try:
                await self._broker.close()
            except Exception:
                logger.exception("Failed to close notification broker")
        self._skipped_runs = 0
        self._last_poll_ts = 0.0
        self._shutting_down = False

    async def disable_runtime(self) -> None:
        """Stop local worker activity while keeping enqueue capabilities alive."""

        self._started = False
        self._loop_enabled = False
        self._use_scheduler_job = False
        self._fatal_error_code = None
        self._fatal_error_at = None
        self._last_delivery_error = None
        await self._stop_watchdog()
        if self._scheduler is not None:
            try:
                self._scheduler.remove_job(self._job_id)
            except Exception:
                pass
        await self._await_scheduler_jobs()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        for task in list(self._poll_tasks):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._poll_tasks.clear()
        self._skipped_runs = 0
        self._last_poll_ts = 0.0

    def _ensure_scheduler_job(self) -> None:
        if self._scheduler is None:
            return

        job = self._scheduler.get_job(self._job_id)
        misfire = max(int(self._current_poll_interval * 2), 1)
        if job is None:
            self._scheduler.add_job(
                run_scheduled_poll,
                "interval",
                seconds=self._current_poll_interval,
                id=self._job_id,
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=misfire,
                next_run_time=datetime.now(timezone.utc),
            )
        else:
            job.modify(max_instances=1, coalesce=True, misfire_grace_time=misfire)
            job.reschedule("interval", seconds=self._current_poll_interval)

        if not self._scheduler.running:
            try:
                self._scheduler.start()
            except SchedulerAlreadyRunningError:
                pass

    async def health_snapshot(self) -> Dict[str, Any]:
        broker_backend = "missing"
        broker_kind = None
        if self._broker is not None:
            broker_kind = self._broker.__class__.__name__
            broker_backend = "redis" if hasattr(self._broker, "_redis") else "memory"
        job_exists = bool(self._scheduler and self._scheduler.get_job(self._job_id))
        watchdog_running = self._watchdog_task is not None and not self._watchdog_task.done()
        seconds_since_poll = None
        if self._last_poll_ts:
            seconds_since_poll = max(0.0, time.monotonic() - self._last_poll_ts)
        rate_limit = None
        rate_capacity = None
        if self._token_bucket is not None:
            rate_limit = self._token_bucket.rate
            rate_capacity = self._token_bucket.capacity
        metrics = await get_notification_metrics_snapshot()
        return {
            "started": self._started,
            "loop_enabled": self._loop_enabled,
            "broker_backend": broker_backend,
            "broker_kind": broker_kind,
            "scheduler_job": job_exists,
            "watchdog_running": watchdog_running,
            "circuit_open": self._is_circuit_open(),
            "seconds_since_poll": seconds_since_poll,
            "rate_limit_per_sec": rate_limit,
            "rate_limit_capacity": rate_capacity,
            "worker_concurrency": self._worker_concurrency,
            "fatal_error_code": self._fatal_error_code,
            "fatal_error_at": (
                self._fatal_error_at.isoformat() if self._fatal_error_at is not None else None
            ),
            "last_delivery_error": self._last_delivery_error,
            "metrics": {
                "outbox_queue_depth": metrics.outbox_queue_depth,
                "poll_skipped_total": metrics.poll_skipped_total,
                "poll_skipped_reasons": metrics.poll_skipped_reasons,
                "poll_backoff_total": metrics.poll_backoff_total,
                "poll_backoff_reasons": metrics.poll_backoff_reasons,
                "poll_staleness_seconds": metrics.poll_staleness_seconds,
                "rate_limit_wait_total": metrics.rate_limit_wait_total,
                "rate_limit_wait_seconds": metrics.rate_limit_wait_seconds,
                "notifications_sent_total": metrics.notifications_sent_total,
                "notifications_failed_total": metrics.notifications_failed_total,
            },
        }

    async def metrics_snapshot(self) -> NotificationMetricsSnapshot:
        return await get_notification_metrics_snapshot()

    async def broker_ping(self) -> Optional[bool]:
        if self._broker is None:
            return None
        redis_client = getattr(self._broker, "_redis", None)
        if redis_client is None:
            return True
        try:
            result = await redis_client.ping()
            return bool(result)
        except Exception:
            logger.exception("notification.worker.broker_ping_failed")
            return False

    async def attach_broker(self, broker: NotificationBrokerProtocol) -> None:
        """Attach (or replace) the notification broker at runtime."""
        if broker is None:
            raise ValueError("broker must not be None")
        try:
            await broker.start()
        except Exception:
            logger.exception("notification.worker.broker_start_failed")
            raise
        if self._broker is not None and self._broker is not broker:
            try:
                await self._broker.close()
            except Exception:
                logger.exception("notification.worker.broker_close_failed")
        self._broker = broker
        self._last_poll_ts = 0.0

    async def detach_broker(self) -> None:
        """Detach current broker (used when Redis becomes unavailable)."""
        if self._broker is None:
            return
        try:
            await self._broker.close()
        except Exception:
            logger.exception("notification.worker.broker_close_failed")
        finally:
            self._broker = None


    async def on_booking_status_changed(
        self,
        booking_id: int,
        status: Any,
        *,
        snapshot: Optional[SlotSnapshot] = None,
    ) -> "NotificationResult":
        raw_status = getattr(status, "value", status)
        try:
            status_value = BookingNotificationStatus(raw_status)
        except (ValueError, TypeError):
            return NotificationResult(status="skipped", reason=f"unsupported_status:{raw_status}")

        if snapshot is None:
            return NotificationResult(status="skipped", reason="missing_snapshot")

        candidate_id = snapshot.candidate_id
        candidate_external_id = getattr(snapshot, "candidate_external_id", None)
        if candidate_id is None and not candidate_external_id:
            return NotificationResult(status="skipped", reason="missing_candidate")

        payload = {
            "event": status_value.value,
            "snapshot": _snapshot_payload(snapshot),
        }

        if status_value is BookingNotificationStatus.RESCHEDULE_REQUESTED:
            return await self._queue_with_direct_fallback(
                notification_type="candidate_reschedule_prompt",
                booking_id=booking_id,
                candidate_id=candidate_id,
                payload=payload,
                snapshot=snapshot,
                status_value=status_value,
                queued_reason="reschedule_prompt_queued",
            )

        if status_value is BookingNotificationStatus.APPROVED:
            return await self._queue_with_direct_fallback(
                notification_type="interview_confirmed_candidate",
                booking_id=booking_id,
                candidate_id=candidate_id,
                payload=payload,
                snapshot=snapshot,
                status_value=status_value,
                queued_reason="interview_confirmed_queued",
            )

        if status_value is BookingNotificationStatus.CANCELLED:
            return await self._queue_with_direct_fallback(
                notification_type="candidate_rejection",
                booking_id=booking_id,
                candidate_id=candidate_id,
                candidate_external_id=candidate_external_id,
                payload=payload,
                snapshot=snapshot,
                status_value=status_value,
                queued_reason="rejection_queued",
            )

        return NotificationResult(status="skipped", reason=status_value.value)

    async def _queue_with_direct_fallback(
        self,
        *,
        notification_type: str,
        booking_id: Optional[int],
        candidate_id: Optional[int],
        payload: Dict[str, Any],
        snapshot: SlotSnapshot,
        status_value: BookingNotificationStatus,
        queued_reason: str,
        candidate_external_id: Optional[str] = None,
    ) -> NotificationResult:
        if candidate_external_id:
            payload = dict(payload)
            payload.setdefault("candidate_external_id", candidate_external_id)
        messenger_channel = "max" if candidate_external_id else "telegram"
        outbox = await add_outbox_notification(
            notification_type=notification_type,
            booking_id=booking_id,
            candidate_tg_id=candidate_id,
            payload=payload,
            messenger_channel=messenger_channel,
        )
        enqueued = await self._enqueue_outbox(outbox.id, attempt=outbox.attempts)
        if enqueued:
            return NotificationResult(status="queued", reason=queued_reason)
        return await self._direct_or_fail(
            notification_type=notification_type,
            status_value=status_value,
            snapshot=snapshot,
            outbox_id=outbox.id,
            outbox_attempts=outbox.attempts,
            booking_id=booking_id or snapshot.slot_id,
            candidate_id=candidate_id,
        )

    async def _direct_or_fail(
        self,
        *,
        notification_type: str,
        status_value: BookingNotificationStatus,
        snapshot: SlotSnapshot,
        outbox_id: int,
        outbox_attempts: int,
        booking_id: Optional[int],
        candidate_id: Optional[int],
    ) -> NotificationResult:
        sent = await self._attempt_direct_delivery(status_value, snapshot)
        if sent:
            await self._finalize_direct_success(
                outbox_id,
                attempts=outbox_attempts,
                booking_id=booking_id,
                notification_type=notification_type,
                candidate_id=candidate_id,
            )
            logger.warning(
                "notification.direct_delivery",
                extra={
                    "notification_type": notification_type,
                    "booking_id": booking_id,
                    "candidate_tg_id": candidate_id,
                },
            )
            return NotificationResult(status="sent", reason=DIRECT_NO_BROKER_REASON)

        await update_outbox_entry(
            outbox_id,
            status="failed",
            attempts=outbox_attempts,
            next_retry_at=None,
            last_error=BROKER_UNAVAILABLE_REASON,
        )
        await record_notification_failed(notification_type)
        logger.error(
            "notification.direct_delivery_failed",
            extra={
                "notification_type": notification_type,
                "booking_id": booking_id,
                "candidate_tg_id": candidate_id,
            },
        )
        return NotificationResult(status="failed", reason=BROKER_UNAVAILABLE_REASON)

    async def _attempt_direct_delivery(
        self,
        status_value: BookingNotificationStatus,
        snapshot: SlotSnapshot,
    ) -> bool:
        await self._throttle()
        if status_value is BookingNotificationStatus.RESCHEDULE_REQUESTED:
            return await _send_reschedule_prompt(snapshot)
        if status_value is BookingNotificationStatus.APPROVED:
            slot = await get_slot(snapshot.slot_id)
            if not slot or not slot.candidate_tg_id:
                return False
            rendered_text, _candidate_tz, _candidate_city, _template_key, _template_version = await _render_candidate_notification(
                slot
            )
            try:
                await _send_with_retry(
                    get_bot(),
                    SendMessage(chat_id=slot.candidate_tg_id, text=rendered_text),
                    correlation_id=f"direct-approve:{slot.id}:{uuid.uuid4().hex}",
                )
            except Exception:
                logger.exception("Failed direct delivery for approved booking", extra={"slot_id": slot.id})
                return False
            try:
                reminder_service = get_reminder_service()
            except RuntimeError:
                reminder_service = None
            if reminder_service is not None:
                await reminder_service.schedule_for_slot(slot.id)
            return True
        if status_value is BookingNotificationStatus.CANCELLED:
            return await _send_final_rejection_notice(snapshot)
        return False

    async def _finalize_direct_success(
        self,
        outbox_id: int,
        *,
        attempts: int,
        booking_id: Optional[int],
        notification_type: str,
        candidate_id: Optional[int],
    ) -> None:
        final_attempts = max(1, attempts + 1)
        await update_outbox_entry(
            outbox_id,
            status="sent",
            attempts=final_attempts,
            next_retry_at=None,
            last_error=None,
        )
        log_type = (
            "candidate_interview_confirmed"
            if notification_type == "interview_confirmed_candidate"
            else notification_type
        )
        if booking_id:
            try:
                await add_notification_log(
                    log_type,
                    booking_id,
                    candidate_tg_id=candidate_id,
                    payload=DIRECT_NO_BROKER_REASON,
                    delivery_status="sent",
                    attempts=final_attempts,
                    last_error=None,
                    overwrite=True,
                )
            except IntegrityError:
                logger.debug(
                    "notification.direct.log_duplicate",
                    extra={"booking_id": booking_id, "notification_type": notification_type},
                )
            except Exception:
                logger.exception(
                    "notification.direct.log_failed",
                    extra={"booking_id": booking_id, "notification_type": notification_type},
                )
        await record_notification_sent(notification_type)

    async def retry_notification(self, outbox_id: int) -> "NotificationResult":
        await reset_outbox_entry(outbox_id)
        success = await self._enqueue_outbox(outbox_id, attempt=0)
        if not success:
            return NotificationResult(status="failed", reason=BROKER_UNAVAILABLE_REASON)
        return NotificationResult(status="queued")

    async def _poll_loop(self) -> None:
        delay = self._current_poll_interval
        try:
            while True:
                try:
                    await self._poll_once()
                    delay = self._current_poll_interval
                    # When broker is enabled, _poll_broker_queue uses a blocking read.
                    # Sleeping here introduces avoidable latency gaps.
                    if self._broker is not None:
                        continue
                except asyncio.CancelledError:
                    raise
                except asyncio.TimeoutError:
                    delay = self._compute_poll_backoff(delay, reason="transient")
                    await record_notification_poll_backoff("transient_error", delay)
                    logger.warning(
                        "notification.worker.loop_iteration_retry",
                        extra={"reason": "timeout", "delay": round(delay, 2)},
                    )
                except Exception:
                    delay = self._compute_poll_backoff(delay, reason="fatal")
                    await record_notification_poll_backoff("fatal_error", delay)
                    logger.exception("notification.worker.loop_iteration_failed")
                    self._open_circuit()
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise

    async def _scheduled_poll(self) -> None:
        current_task = asyncio.current_task()
        if current_task is not None:
            self._scheduler_jobs.add(current_task)
        self._poll_tasks = {task for task in self._poll_tasks if not task.done()}
        try:
            if not self._started or self._shutting_down:
                return
            if len(self._poll_tasks) >= self._worker_concurrency:
                await self._handle_poll_skipped(reason="lock_busy")
                return
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.warning("notification.worker.loop_unavailable")
                await self._handle_poll_skipped(reason="no_loop")
                return

            if self._shutting_down:
                return
            task = loop.create_task(self._poll_once())
            self._poll_tasks.add(task)
            task.add_done_callback(self._on_poll_task_done)
        finally:
            if current_task is not None:
                self._scheduler_jobs.discard(current_task)

    def _on_poll_task_done(self, task: asyncio.Task) -> None:
        self._poll_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.exception("notification.worker.poll_failed", exc_info=exc)

    async def _handle_poll_skipped(self, *, reason: str) -> None:
        self._skipped_runs += 1
        duration_ms = None
        if self._last_poll_ts:
            duration_ms = int(max(0.0, time.monotonic() - self._last_poll_ts) * 1000)
        logger.info(
            "notification.worker.poll_skipped",
            extra={
                "reason": reason,
                "skipped_total": self._skipped_runs,
                "duration_ms": duration_ms,
            },
        )
        await record_notification_poll_skipped(reason=reason, skipped_total=self._skipped_runs)

    async def _poll_once(self) -> None:
        start = time.perf_counter()
        processed = 0
        source = "idle"
        started_at = datetime.now(timezone.utc).isoformat()
        broker_available = self._broker is not None

        logger.info(
            "notification.worker.poll_start",
            extra={"started_at": started_at, "skipped_total": self._skipped_runs},
        )

        previous_poll_ts = self._last_poll_ts
        try:
            async with self._poll_gate:
                if self._broker is not None:
                    processed, source = await self._poll_broker_queue()
                else:
                    processed, source = await self._poll_outbox_queue()
        except Exception as exc:
            source = f"error:{exc.__class__.__name__}"
            logger.exception(
                "notification.worker.poll_error",
                extra={
                    "started_at": started_at,
                    "duration_ms": int((time.perf_counter() - start) * 1000),
                },
            )
            await set_outbox_queue_depth(0)
        finally:
            duration = time.perf_counter() - start
            now_ts = time.monotonic()
            seconds_since_prev = 0.0
            if previous_poll_ts:
                seconds_since_prev = max(0.0, now_ts - previous_poll_ts)
            self._last_poll_ts = now_ts
            if processed == 0 and source in {"broker_idle", "outbox_idle", "db_unavailable"}:
                now = time.monotonic()
                if now - self._last_idle_log_ts >= self._idle_log_interval:
                    self._last_idle_log_ts = now
                    logger.info(
                        "notification.worker.poll_cycle processed=%s source=%s skipped_total=%s",
                        processed,
                        source,
                        self._skipped_runs,
                        extra={
                            "started_at": started_at,
                            "duration_ms": int(duration * 1000),
                            "processed": processed,
                            "source": source,
                            "skipped_total": self._skipped_runs,
                        },
                    )
                    if source == "db_unavailable":
                        idle_reason = "db_unavailable"
                    else:
                        idle_reason = "broker_unavailable" if not broker_available else "no_work"
                    logger.info(
                        "notification.worker.poll_skipped",
                        extra={
                            "reason": idle_reason,
                            "skipped_total": self._skipped_runs,
                            "duration_ms": int(duration * 1000),
                        },
                    )
            else:
                logger.info(
                    "notification.worker.poll_cycle processed=%s source=%s skipped_total=%s",
                    processed,
                    source,
                    self._skipped_runs,
                    extra={
                        "started_at": started_at,
                        "duration_ms": int(duration * 1000),
                        "processed": processed,
                        "source": source,
                        "skipped_total": self._skipped_runs,
                    },
                )
            if processed > 0:
                self._reset_idle_backoff()
            elif source == "broker_idle":
                self._advance_idle_backoff(reason="broker_idle")
            elif source == "db_unavailable":
                self._advance_idle_backoff(reason="db_unavailable")
            await record_notification_poll_cycle(
                duration=duration,
                processed=processed,
                source=source,
                skipped_total=self._skipped_runs,
                seconds_since_poll=seconds_since_prev,
            )
            await record_notification_poll_staleness(0.0)

    async def _process_broker_message(self, message: BrokerMessage) -> None:
        if self._broker is None:
            return
        now = time.time()
        not_before = message.not_before()
        if not_before is not None and not_before > now:
            delay = max(0.0, not_before - now)
            try:
                await self._broker.requeue(message, delay_seconds=delay)
            finally:
                await self._broker.ack(message.id)
            return

        outbox_id_raw = message.payload.get("outbox_id")
        try:
            outbox_id = int(outbox_id_raw)
        except (TypeError, ValueError):
            await self._broker.ack(message.id)
            return

        item = await claim_outbox_item_by_id(outbox_id)
        if item is None:
            await self._broker.ack(message.id)
            return

        broker_attempt = message.attempts()
        if broker_attempt and broker_attempt > item.attempts:
            item.attempts = broker_attempt

        try:
            await self._process_item(item, broker_message=message)
        finally:
            await self._broker.ack(message.id)

    async def _enqueue_outbox(
        self,
        outbox_id: int,
        *,
        attempt: int = 0,
        delay: float = 0.0,
    ) -> bool:
        if self._broker is None:
            logger.error(
                "notification.worker.enqueue_missing_broker",
                extra={"outbox_id": outbox_id, "attempt": attempt},
            )
            return False
        payload = {
            "outbox_id": outbox_id,
            "attempt": max(0, int(attempt)),
            "max_attempts": self._max_attempts,
        }
        try:
            await self._broker.publish(payload, delay_seconds=delay)
            return True
        except Exception:
            logger.exception(
                "notification.worker.enqueue_failed",
                extra={"outbox_id": outbox_id, "attempt": attempt},
            )
            return False

    async def _enqueue_due_outbox_batch(self) -> int:
        if self._broker is None:
            return 0

        items = await claim_outbox_batch(batch_size=self._batch_size)
        if not items:
            return 0

        enqueued = 0
        for item in items:
            delay = 0.0
            if item.next_retry_at is not None:
                next_retry = item.next_retry_at
                if isinstance(next_retry, datetime) and next_retry.tzinfo is None:
                    next_retry = next_retry.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                delay = max(0.0, (next_retry - now).total_seconds())
            success = await self._enqueue_outbox(
                item.id,
                attempt=item.attempts,
                delay=delay,
            )
            if success:
                enqueued += 1
            # Release claim lock after broker publish attempt.
            # Broker delivery will claim by outbox_id before processing.
            await update_outbox_entry(
                item.id,
                attempts=item.attempts,
                last_error=None,
            )
        return enqueued

    async def _poll_broker_queue(self) -> Tuple[int, str]:
        if self._broker is None:
            return 0, "broker_unavailable"

        block_ms = int(self._current_poll_interval * 1000)
        messages = await self._broker.read(count=self._batch_size, block_ms=block_ms)
        source = "broker"

        if not messages:
            source = "broker_idle"
            messages = await self._broker.claim_stale(
                min_idle_ms=self._claim_idle_ms,
                count=self._batch_size,
            )

        if not messages:
            try:
                enqueued = await self._enqueue_due_outbox_batch()
            except (OperationalError, ConnectionRefusedError, OSError) as exc:
                self._record_db_unavailable(exc, context="enqueue_due_outbox_batch")
                return 0, "db_unavailable"
            if enqueued:
                source = "broker_bootstrap"
                messages = await self._broker.read(count=self._batch_size, block_ms=block_ms)

        if messages:
            processed = len(messages)
            await set_outbox_queue_depth(processed)
            try:
                for message in messages:
                    await self._process_broker_message(message)
            finally:
                await set_outbox_queue_depth(0)
            return processed, source

        try:
            items = await claim_outbox_batch(batch_size=self._batch_size)
        except (OperationalError, ConnectionRefusedError, OSError) as exc:
            self._record_db_unavailable(exc, context="claim_outbox_batch")
            await set_outbox_queue_depth(0)
            return 0, "db_unavailable"
        if not items:
            await set_outbox_queue_depth(0)
            return 0, source

        processed = len(items)
        await set_outbox_queue_depth(processed)
        try:
            for item in items:
                await self._process_item(item)
        finally:
            await set_outbox_queue_depth(0)
        return processed, "outbox_fallback"

    async def _poll_outbox_queue(self) -> Tuple[int, str]:
        try:
            items = await claim_outbox_batch(batch_size=self._batch_size)
        except (OperationalError, ConnectionRefusedError, OSError) as exc:
            self._record_db_unavailable(exc, context="claim_outbox_batch")
            await set_outbox_queue_depth(0)
            return 0, "db_unavailable"
        if not items:
            await set_outbox_queue_depth(0)
            return 0, "outbox_idle"

        processed = len(items)
        await set_outbox_queue_depth(processed)
        try:
            for item in items:
                await self._process_item(item)
        finally:
            await set_outbox_queue_depth(0)
        return processed, "outbox"

    async def _send_via_messenger_adapter(
        self,
        item: OutboxItem,
        chat_id: int | str,
        text: str,
        *,
        buttons: Optional[list] = None,
        parse_mode: Optional[str] = None,
    ) -> SendResult:
        """Send a message using the messenger abstraction layer.

        If the outbox item's messenger_channel is not 'telegram' (or when
        called explicitly), this method routes through the adapter registry
        instead of the aiogram Bot directly.

        Returns True on success, False on failure (already schedules retry).
        """
        try:
            from backend.core.messenger.registry import get_registry
            from backend.core.messenger.protocol import MessengerPlatform, InlineButton

            channel = getattr(item, "messenger_channel", "telegram") or "telegram"
            platform = MessengerPlatform.from_str(channel)
            registry = get_registry()
            adapter = registry.get(platform)

            if adapter is None:
                logger.warning(
                    "notification.messenger_adapter.not_found",
                    extra={"channel": channel, "outbox_id": item.id},
                )
                return SendResult(success=False, error="adapter_missing")

            # Convert button format if provided
            adapter_buttons = None
            if buttons:
                adapter_buttons = []
                for row in buttons:
                    adapter_row = []
                    for btn in row:
                        if not hasattr(btn, "text"):
                            continue
                        web_app = getattr(btn, "web_app", None)
                        kind = getattr(btn, "kind", None)
                        if web_app is not None and getattr(web_app, "url", None):
                            adapter_row.append(
                                InlineButton(
                                    text=btn.text,
                                    url=web_app.url,
                                    kind=kind or "web_app",
                                )
                            )
                            continue
                        if getattr(btn, "url", None):
                            adapter_row.append(
                                InlineButton(
                                    text=btn.text,
                                    url=getattr(btn, "url", None),
                                    kind=kind or "link",
                                )
                            )
                            continue
                        if hasattr(btn, "callback_data"):
                            adapter_row.append(
                                InlineButton(
                                    text=btn.text,
                                    callback_data=btn.callback_data,
                                    kind=kind or "callback",
                                )
                            )
                    if adapter_row:
                        adapter_buttons.append(adapter_row)

            result = await adapter.send_message(
                chat_id,
                text,
                buttons=adapter_buttons,
                parse_mode=parse_mode,
                correlation_id=f"outbox:{item.type}:{item.id}",
            )
            return result
        except Exception:
            logger.exception(
                "notification.messenger_adapter.error",
                extra={"outbox_id": item.id},
            )
            return SendResult(success=False, error="adapter_exception")

    def _is_non_telegram_channel(self, item: OutboxItem) -> bool:
        """Check if the outbox item should be routed via a non-Telegram adapter."""
        channel = getattr(item, "messenger_channel", "telegram") or "telegram"
        return channel != "telegram"

    async def _resolve_adapter_recipient(self, item: OutboxItem) -> int | str | None:
        channel = getattr(item, "messenger_channel", "telegram") or "telegram"
        if channel == "max":
            payload = dict(item.payload or {})
            candidate_external_id = str(payload.get("candidate_external_id") or "").strip()
            if candidate_external_id:
                return candidate_external_id

            candidate_id = str(payload.get("candidate_id") or "").strip()
            if not candidate_id and item.booking_id:
                async with async_session() as session:
                    slot = await session.get(Slot, int(item.booking_id))
                    if slot is not None and getattr(slot, "candidate_id", None):
                        candidate_id = str(slot.candidate_id).strip()
            if candidate_id:
                async with async_session() as session:
                    max_user_id = await session.scalar(
                        select(User.max_user_id).where(User.candidate_id == candidate_id)
                    )
                    if max_user_id:
                        return str(max_user_id)
            if item.candidate_tg_id is not None:
                return item.candidate_tg_id
            return None

        if item.candidate_tg_id is not None:
            return item.candidate_tg_id
        return None

    async def _process_via_adapter(self, item: OutboxItem) -> None:
        """Generic handler for non-telegram channels.

        Renders the template for the notification type and sends the text
        through the messenger adapter layer. Inline buttons that use Telegram
        callback_data are converted to the adapter's button format.
        """
        recipient_id = await self._resolve_adapter_recipient(item)
        if not recipient_id:
            await self._mark_failed(
                item, item.attempts, item.type, item.type,
                "candidate_missing", None, candidate_tg_id=None,
            )
            return

        # Try to render a template for this notification type
        payload = dict(item.payload or {})
        context = dict(payload)  # pass payload vars as template context
        rendered = await self._template_provider.render(item.type, context)
        if rendered is None:
            # Fallback: use raw text from payload if template is missing
            text = payload.get("text") or payload.get("message")
            if not text:
                await self._mark_failed(
                    item, item.attempts, item.type, item.type,
                    "template_missing_and_no_fallback_text", None,
                    candidate_tg_id=item.candidate_tg_id,
                )
                return
        else:
            text = rendered.text

        attempt = item.attempts + 1
        result = await self._send_via_messenger_adapter(item, recipient_id, text)
        if result.success:
            await self._mark_sent(
                item,
                attempt,
                item.type,
                item.type,
                rendered,
                item.candidate_tg_id,
                provider_message_id=result.message_id,
            )
        else:
            await self._schedule_retry(
                item, attempt=attempt, log_type=item.type,
                notification_type=item.type, error=result.error or "adapter_send_failed",
                rendered=rendered, candidate_tg_id=item.candidate_tg_id,
            )

    async def _process_item(self, item: OutboxItem, *, broker_message: Optional[BrokerMessage] = None) -> None:
        handlers = {
            "interview_confirmed_candidate": self._process_candidate_confirmation,
            "candidate_reschedule_prompt": self._process_candidate_reschedule,
            "candidate_rejection": self._process_candidate_rejection,
            "recruiter_candidate_confirmed_notice": self._process_recruiter_notice,
            "interview_reminder_2h": self._process_interview_reminder,
            "slot_reminder": self._process_interview_reminder,
            "intro_day_invitation": self._process_intro_day_invitation,
            "test2_completed": self._process_test2_completed,
            "slot_proposal": self._process_slot_proposal,
            "slot_confirmed_recruiter": self._process_slot_confirmed_recruiter,
            "reschedule_requested_recruiter": self._process_reschedule_requested_recruiter,
            "reschedule_approved_candidate": self._process_reschedule_approved_candidate,
            "reschedule_declined_candidate": self._process_reschedule_declined_candidate,
            "slot_assignment_offer": self._process_slot_assignment_offer,
            "slot_assignment_reschedule_approved": self._process_slot_assignment_reschedule_approved,
            "slot_assignment_reschedule_declined": self._process_slot_assignment_reschedule_declined,
            "slot_assignment_reschedule_requested": self._process_slot_assignment_reschedule_requested,
        }
        handler = handlers.get(item.type)
        previous_message = self._current_message
        self._current_message = broker_message
        try:
            # Route non-telegram channels through the messenger adapter layer.
            # This renders the template the same way but sends via the platform
            # adapter instead of the aiogram Bot.
            if self._is_non_telegram_channel(item):
                await self._process_via_adapter(item)
                return

            if handler is None:
                await self._mark_failed(
                    item,
                    item.attempts,
                    item.type,
                    item.type,
                    f"unsupported_type:{item.type}",
                    None,
                    candidate_tg_id=item.candidate_tg_id,
                )
                return
            await handler(item)
        except TelegramUnauthorizedError:
            await self._mark_failed(
                item,
                max(1, item.attempts + 1),
                item.type,
                item.type,
                "telegram_unauthorized",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
        except Exception as exc:
            logger.exception(
                "notification.worker.process_item_error",
                extra={
                    "outbox_id": item.id,
                    "notification_type": item.type,
                    "booking_id": item.booking_id,
                    "candidate_tg_id": item.candidate_tg_id,
                },
            )
            await self._schedule_retry(
                item,
                attempt=item.attempts + 1,
                log_type=item.type,
                notification_type=item.type,
                error=f"unexpected:{exc.__class__.__name__}",
                rendered=None,
                candidate_tg_id=item.candidate_tg_id,
            )
        finally:
            self._current_message = previous_message

    async def _has_sent_log(
        self,
        log_type: str,
        booking_id: Optional[int],
        candidate_tg_id: Optional[int],
    ) -> bool:
        if booking_id is None:
            return False
        existing = await get_notification_log(
            log_type, booking_id, candidate_tg_id=candidate_tg_id
        )
        return existing is not None and getattr(existing, "delivery_status", "") == "sent"

    async def _process_slot_proposal(self, item: OutboxItem) -> None:
        """Processes a slot proposal notification to a candidate."""
        payload = dict(item.payload or {})
        candidate_id = item.candidate_tg_id
        if not candidate_id:
            await self._mark_failed(item, item.attempts, "slot_proposal", "slot_proposal", "candidate_missing", None, candidate_tg_id=None)
            return

        assignment_id = payload.get("assignment_id")
        start_utc_str = payload.get("start_utc")

        if not assignment_id or not start_utc_str:
            await self._mark_failed(item, item.attempts, "slot_proposal", "slot_proposal", "payload_incomplete", None, candidate_tg_id=candidate_id)
            return

        start_utc = datetime.fromisoformat(start_utc_str)

        context = {"dt_local": fmt_dt_local(start_utc, "Europe/Moscow")} # Assume Moscow, should be candidate's TZ
        rendered = await self._template_provider.render("slot_proposal_candidate", context)

        if rendered is None:
            await self._mark_failed(item, item.attempts, "slot_proposal", "slot_proposal", "template_missing", None, candidate_tg_id=candidate_id)
            return

        controls = None
        try:
            controls = await get_candidate_assignment_controls(
                candidate_tg_id=int(candidate_id),
                assignment_id=int(assignment_id),
            )
        except Exception:
            logger.exception(
                "slot_proposal.controls_build_failed",
                extra={"assignment_id": assignment_id, "candidate_id": candidate_id},
            )
        if controls is not None and controls.confirm_token and controls.reschedule_token:
            keyboard = kb_slot_assignment_offer(
                controls.assignment_id,
                confirm_token=controls.confirm_token,
                reschedule_token=controls.reschedule_token,
                decline_token=controls.decline_token,
            )
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_assignment:{assignment_id}")],
                [InlineKeyboardButton(text="🗓️ Другое время", callback_data=f"reschedule_assignment:{assignment_id}")]
            ])

        attempt = item.attempts + 1
        try:
            await get_bot().send_message(candidate_id, rendered.text, reply_markup=keyboard)
        except Exception as exc:
            await self._schedule_retry(item, attempt=attempt, log_type="slot_proposal", notification_type="slot_proposal", error=str(exc), rendered=rendered, candidate_tg_id=candidate_id)
            return

        await self._mark_sent(item, attempt, "slot_proposal", "slot_proposal", rendered, candidate_id)

    async def _process_slot_confirmed_recruiter(self, item: OutboxItem) -> None:
        """Notifies a recruiter that a candidate has confirmed a slot."""
        recruiter_chat_id = item.recruiter_tg_id
        if not recruiter_chat_id:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_confirmed_recruiter",
                "slot_confirmed_recruiter",
                "recruiter_missing",
                None,
            )
            return

        payload = dict(item.payload or {})
        slot_id = payload.get("slot_id") or item.booking_id
        slot = await get_slot(int(slot_id)) if slot_id else None
        candidate_name = "Кандидат"
        dt_local = None
        if slot is not None:
            candidate_name = slot.candidate_fio or slot.candidate_id or candidate_name
            dt_local = fmt_dt_local(slot.start_utc, slot.candidate_tz or DEFAULT_TZ)

        context = {
            "candidate_name": escape_html(str(candidate_name)),
            "dt_local": dt_local or "",
        }
        rendered = await self._template_provider.render("slot_confirmed_recruiter", context)
        text = rendered.text if rendered is not None else "Кандидат подтвердил слот."

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await _send_with_retry(
                get_bot(),
                SendMessage(chat_id=recruiter_chat_id, text=text),
                correlation_id=f"outbox:{item.type}:{item.id}:{uuid.uuid4().hex}",
            )
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="slot_confirmed_recruiter",
                notification_type="slot_confirmed_recruiter",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        self._last_delivery_error = None
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )
        await record_notification_sent("slot_confirmed_recruiter")

    async def _process_reschedule_requested_recruiter(self, item: OutboxItem) -> None:
        """Notifies a recruiter that a candidate has requested a reschedule."""
        recruiter_chat_id = item.recruiter_tg_id
        if not recruiter_chat_id:
            await self._mark_failed(
                item,
                item.attempts,
                "reschedule_requested_recruiter",
                "reschedule_requested_recruiter",
                "recruiter_missing",
                None,
            )
            return

        payload = dict(item.payload or {})
        assignment_id_raw = payload.get("slot_assignment_id") or payload.get("assignment_id")
        assignment_id = None
        try:
            assignment_id = int(assignment_id_raw) if assignment_id_raw is not None else None
        except (TypeError, ValueError):
            assignment_id = None

        if assignment_id is None and item.booking_id is None and payload.get("slot_id") is None:
            await self._mark_failed(
                item,
                max(1, item.attempts + 1),
                "reschedule_requested_recruiter",
                "reschedule_requested_recruiter",
                "context_missing",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        assignment = None
        # Legacy outbox entries may outlive their originating assignment; don't spam recruiters in that case.
        if assignment_id is not None:
            from backend.domain.models import SlotAssignment
            from backend.core.db import async_session

            async with async_session() as session:
                assignment = await session.get(SlotAssignment, assignment_id)
            if assignment is None:
                await self._mark_failed(
                    item,
                    max(1, item.attempts + 1),
                    "reschedule_requested_recruiter",
                    "reschedule_requested_recruiter",
                    "assignment_missing",
                    None,
                    candidate_tg_id=item.candidate_tg_id,
                )
                return
        candidate_tg_id = item.candidate_tg_id or getattr(assignment, "candidate_tg_id", None)

        requested_raw = (
            payload.get("requested_start_utc")
            or payload.get("requested_time_utc")
            or payload.get("requested_time")
        )
        requested_utc = None
        if requested_raw:
            try:
                requested_utc = datetime.fromisoformat(str(requested_raw))
                if requested_utc.tzinfo is None:
                    requested_utc = requested_utc.replace(tzinfo=timezone.utc)
                else:
                    requested_utc = requested_utc.astimezone(timezone.utc)
            except Exception:
                requested_utc = None

        recruiter = await get_recruiter_by_chat_id(recruiter_chat_id)
        tz_label = (getattr(recruiter, "tz", None) or DEFAULT_TZ) if recruiter else DEFAULT_TZ
        requested_time_local = (
            fmt_dt_local(requested_utc, tz_label) if requested_utc is not None else ""
        )
        candidate_name = payload.get("candidate_name") or payload.get("candidate_fio")
        if not candidate_name:
            slot_id_raw = payload.get("slot_id") or item.booking_id or getattr(assignment, "slot_id", None)
            try:
                slot_id = int(slot_id_raw) if slot_id_raw is not None else None
            except (TypeError, ValueError):
                slot_id = None

            if slot_id is not None:
                from backend.domain.models import Slot
                from backend.core.db import async_session

                async with async_session() as session:
                    slot = await session.get(Slot, slot_id)
                if slot is not None and getattr(slot, "candidate_fio", None):
                    candidate_name = slot.candidate_fio
                if candidate_tg_id is None:
                    candidate_tg_id = getattr(slot, "candidate_tg_id", None)

        if not candidate_name:
            candidate_name = getattr(assignment, "candidate_id", None) or (
                str(candidate_tg_id) if candidate_tg_id is not None else None
            )

        if not candidate_name:
            await self._mark_failed(
                item,
                max(1, item.attempts + 1),
                "reschedule_requested_recruiter",
                "reschedule_requested_recruiter",
                "candidate_missing",
                None,
                candidate_tg_id=candidate_tg_id,
            )
            return

        context = {
            "candidate_name": escape_html(str(candidate_name)),
            "requested_time_local": requested_time_local,
        }
        rendered = await self._template_provider.render("reschedule_requested_recruiter", context)
        if rendered is not None and rendered.text:
            text = rendered.text
        else:
            details = []
            if candidate_name:
                details.append(f"👤 {escape_html(str(candidate_name))}")
            if requested_time_local:
                details.append(f"🗓 {escape_html(str(requested_time_local))}")
            if details:
                text = "🔁 Кандидат запросил другое время\n" + "\n".join(details)
            else:
                text = "Кандидат запросил другое время."

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await _send_with_retry(
                get_bot(),
                SendMessage(chat_id=recruiter_chat_id, text=text),
                correlation_id=f"outbox:{item.type}:{item.id}:{uuid.uuid4().hex}",
            )
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="reschedule_requested_recruiter",
                notification_type="reschedule_requested_recruiter",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_tg_id,
            )
            return

        self._last_delivery_error = None
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )
        await record_notification_sent("reschedule_requested_recruiter")
        
    async def _process_reschedule_approved_candidate(self, item: OutboxItem) -> None:
        """Notifies a candidate their reschedule request was approved."""
        candidate_id = item.candidate_tg_id
        if not candidate_id:
            await self._mark_failed(
                item,
                item.attempts,
                "reschedule_approved_candidate",
                "reschedule_approved_candidate",
                "candidate_missing",
                None,
                candidate_tg_id=None,
            )
            return

        payload = dict(item.payload or {})
        new_time_raw = payload.get("new_time_utc") or payload.get("new_start_utc")
        new_time_utc = None
        if new_time_raw:
            try:
                new_time_utc = datetime.fromisoformat(str(new_time_raw))
                if new_time_utc.tzinfo is None:
                    new_time_utc = new_time_utc.replace(tzinfo=timezone.utc)
                else:
                    new_time_utc = new_time_utc.astimezone(timezone.utc)
            except Exception:
                new_time_utc = None

        tz_label = payload.get("candidate_tz") or DEFAULT_TZ
        new_time_local = fmt_dt_local(new_time_utc, tz_label) if new_time_utc else ""
        context = {"new_time_local": new_time_local}
        rendered = await self._template_provider.render("reschedule_approved_candidate", context)
        text = rendered.text if rendered is not None else "Ваш запрос на перенос одобрен."

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await _send_with_retry(
                get_bot(),
                SendMessage(chat_id=candidate_id, text=text),
                correlation_id=f"outbox:{item.type}:{item.id}:{uuid.uuid4().hex}",
            )
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="reschedule_approved_candidate",
                notification_type="reschedule_approved_candidate",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        self._last_delivery_error = None
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )
        await record_notification_sent("reschedule_approved_candidate")

    async def _process_reschedule_declined_candidate(self, item: OutboxItem) -> None:
        """Notifies a candidate their reschedule request was declined."""
        candidate_id = item.candidate_tg_id
        if not candidate_id:
            await self._mark_failed(
                item,
                item.attempts,
                "reschedule_declined_candidate",
                "reschedule_declined_candidate",
                "candidate_missing",
                None,
                candidate_tg_id=None,
            )
            return

        payload = dict(item.payload or {})
        recruiter_comment = payload.get("recruiter_comment") or ""
        context = {"recruiter_comment": escape_html(str(recruiter_comment))}
        rendered = await self._template_provider.render("reschedule_declined_candidate", context)
        text = rendered.text if rendered is not None else "Ваш запрос на перенос отклонен."

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await _send_with_retry(
                get_bot(),
                SendMessage(chat_id=candidate_id, text=text),
                correlation_id=f"outbox:{item.type}:{item.id}:{uuid.uuid4().hex}",
            )
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="reschedule_declined_candidate",
                notification_type="reschedule_declined_candidate",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        self._last_delivery_error = None
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )
        await record_notification_sent("reschedule_declined_candidate")

    async def _process_candidate_confirmation(self, item: OutboxItem) -> None:
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        if not slot or slot.candidate_tg_id != item.candidate_tg_id:
            await self._mark_failed(
                item,
                item.attempts,
                "candidate_interview_confirmed",
                "interview_confirmed_candidate",
                "slot_mismatch",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        candidate_id = slot.candidate_tg_id
        if await self._has_sent_log("candidate_interview_confirmed", slot.id, candidate_id):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        rendered_text, _candidate_tz, _candidate_city, template_key, template_version = await _render_candidate_notification(
            slot
        )
        rendered_payload = SimpleNamespace(
            text=rendered_text,
            key=template_key or "interview_confirmed_candidate",
            version=template_version,
        )
        attempt = item.attempts + 1
        await self._ensure_log(
            "candidate_interview_confirmed",
            item,
            attempt,
            rendered_payload,
            candidate_id,
        )

        if self._is_circuit_open():
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_interview_confirmed",
                notification_type="interview_confirmed_candidate",
                error="circuit_open",
                rendered=rendered_payload,
                retry_after=self._breaker_remaining(),
                candidate_tg_id=candidate_id,
                count_failure=False,
            )
            return

        await self._throttle()

        bot = get_bot()
        reply_markup = None
        try:
            reply_markup = await build_candidate_active_meeting_keyboard_for_slot(slot)
        except Exception:
            logger.exception(
                "candidate_confirmation.controls_build_failed",
                extra={"slot_id": slot.id, "candidate_id": candidate_id},
            )
        try:
            logger.info(
                "notification.worker.send_attempt send_callable=%s",
                _send_with_retry,
                extra={
                    "notification_type": "candidate_interview_confirmed",
                    "candidate_id": candidate_id,
                    "booking_id": slot.id,
                },
            )
            await _send_with_retry(
                bot,
                SendMessage(chat_id=candidate_id, text=rendered_text, reply_markup=reply_markup),
                correlation_id=f"outbox:{slot.id}:{uuid.uuid4().hex}",
            )
        except TelegramRetryAfter as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_interview_confirmed",
                notification_type="interview_confirmed_candidate",
                error=str(exc),
                rendered=rendered_payload,
                retry_after=exc.retry_after,
                candidate_tg_id=candidate_id,
            )
            return
        except (TelegramServerError, asyncio.TimeoutError, ClientError) as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_interview_confirmed",
                notification_type="interview_confirmed_candidate",
                error=str(exc),
                rendered=rendered_payload,
                candidate_tg_id=candidate_id,
            )
            return
        except TelegramBadRequest as exc:
            await self._mark_failed(
                item,
                attempt,
                "candidate_interview_confirmed",
                "interview_confirmed_candidate",
                str(exc),
                rendered_payload,
                candidate_tg_id=candidate_id,
            )
            return
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_interview_confirmed",
                notification_type="interview_confirmed_candidate",
                error=str(exc),
                rendered=rendered_payload,
                candidate_tg_id=candidate_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            "candidate_interview_confirmed",
            "interview_confirmed_candidate",
            rendered_payload,
            candidate_id,
        )

        try:
            reminder_service = get_reminder_service()
        except RuntimeError:
            reminder_service = None
        if reminder_service is not None and item.booking_id is not None:
            await reminder_service.schedule_for_slot(item.booking_id)

    async def _process_test2_completed(self, item: OutboxItem) -> None:
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=item.attempts,
            next_retry_at=None,
            last_error=None,
        )

    async def _process_candidate_reschedule(self, item: OutboxItem) -> None:
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        snapshot: Optional[SlotSnapshot]

        if slot is not None and slot.candidate_tg_id == item.candidate_tg_id:
            snapshot = await _build_slot_snapshot(slot)
        else:
            payload_snapshot = _snapshot_from_payload((item.payload or {}).get("snapshot"))
            if payload_snapshot is not None and payload_snapshot.candidate_id != item.candidate_tg_id:
                payload_snapshot = None
            snapshot = payload_snapshot

        if snapshot is None or snapshot.candidate_id is None:
            await self._mark_failed(
                item,
                item.attempts,
                "candidate_reschedule_prompt",
                "candidate_reschedule_prompt",
                "snapshot_unavailable",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        if not snapshot.slot_id and item.booking_id is not None:
            snapshot.slot_id = item.booking_id

        candidate_id = snapshot.candidate_id
        if await self._has_sent_log(
            "candidate_reschedule_prompt",
            item.booking_id,
            candidate_id,
        ):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        context = {
            "candidate_name": snapshot.candidate_fio or str(candidate_id or ""),
            "recruiter_name": snapshot.recruiter_name,
            "dt_local": TemplateProvider.format_local_dt(
                snapshot.start_utc, snapshot.candidate_tz
            ),
            "tz_name": snapshot.candidate_tz,
            "join_link": "",
        }
        rendered = await self._template_provider.render(
            "candidate_reschedule_prompt",
            context,
            city_id=snapshot.candidate_city_id,
        )
        if rendered is None:
            await self._mark_failed(
                item,
                item.attempts,
                "candidate_reschedule_prompt",
                "candidate_reschedule_prompt",
                "template_missing",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        attempt = item.attempts + 1
        await self._ensure_log(
            "candidate_reschedule_prompt",
            item,
            attempt,
            rendered,
            candidate_id,
        )

        await self._throttle()
        sent = await self._send_reschedule_message(snapshot, rendered.text)
        if not sent:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_reschedule_prompt",
                notification_type="candidate_reschedule_prompt",
                error="bot_unavailable",
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            "candidate_reschedule_prompt",
            "candidate_reschedule_prompt",
            rendered,
            candidate_id,
        )

    async def _process_candidate_rejection(self, item: OutboxItem) -> None:
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        snapshot: Optional[SlotSnapshot]

        if slot is not None and slot.candidate_tg_id == item.candidate_tg_id:
            snapshot = await _build_slot_snapshot(slot)
        else:
            payload_snapshot = _snapshot_from_payload((item.payload or {}).get("snapshot"))
            if payload_snapshot is not None and payload_snapshot.candidate_id != item.candidate_tg_id:
                payload_snapshot = None
            snapshot = payload_snapshot

        if snapshot is None or snapshot.candidate_id is None:
            await self._mark_failed(
                item,
                item.attempts,
                "candidate_rejection",
                "candidate_rejection",
                "snapshot_unavailable",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        if not snapshot.slot_id and item.booking_id is not None:
            snapshot.slot_id = item.booking_id

        candidate_id = snapshot.candidate_id
        if await self._has_sent_log("candidate_rejection", item.booking_id, candidate_id):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        state = await _load_candidate_state(candidate_id)
        context = {
            "candidate_name": snapshot.candidate_fio or state.get("fio") or str(candidate_id or ""),
            "recruiter_name": snapshot.recruiter_name,
            "dt_local": TemplateProvider.format_local_dt(
                snapshot.start_utc, snapshot.candidate_tz
            ),
            "tz_name": snapshot.candidate_tz,
            "join_link": "",
            "status": "отклонена",
            "booking_id": snapshot.slot_id or item.booking_id or "",
        }
        rendered = await self._template_provider.render(
            "candidate_rejection",
            context,
            city_id=snapshot.candidate_city_id,
        )
        if rendered is None:
            await self._mark_failed(
                item,
                item.attempts,
                "candidate_rejection",
                "candidate_rejection",
                "template_missing",
                None,
                candidate_tg_id=candidate_id,
            )
            return
        if _uses_legacy_status_update_text(rendered.text):
            from backend.apps.bot.defaults import DEFAULT_TEMPLATES
            from backend.utils.jinja_renderer import render_template

            rendered = RenderedTemplate(
                key="candidate_rejection",
                version=0,
                city_id=snapshot.candidate_city_id,
                text=render_template(DEFAULT_TEMPLATES["candidate_rejection"], context),
            )

        attempt = item.attempts + 1
        await self._ensure_log(
            "candidate_rejection",
            item,
            attempt,
            rendered,
            candidate_id,
        )

        if self._is_circuit_open():
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_rejection",
                notification_type="candidate_rejection",
                error="circuit_open",
                rendered=rendered,
                retry_after=self._breaker_remaining(),
                candidate_tg_id=candidate_id,
                count_failure=False,
            )
            return

        await self._throttle()

        bot = get_bot()
        try:
            await _send_with_retry(
                bot,
                SendMessage(chat_id=candidate_id, text=rendered.text),
                correlation_id=f"outbox:{snapshot.slot_id}:{uuid.uuid4().hex}",
            )
        except TelegramRetryAfter as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_rejection",
                notification_type="candidate_rejection",
                error=str(exc),
                rendered=rendered,
                retry_after=exc.retry_after,
                candidate_tg_id=candidate_id,
            )
            return
        except (TelegramServerError, asyncio.TimeoutError, ClientError) as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_rejection",
                notification_type="candidate_rejection",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except TelegramBadRequest as exc:
            await self._mark_failed(
                item,
                attempt,
                "candidate_rejection",
                "candidate_rejection",
                str(exc),
                rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="candidate_rejection",
                notification_type="candidate_rejection",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            "candidate_rejection",
            "candidate_rejection",
            rendered,
            candidate_id,
        )
        await self._mark_candidate_rejected(candidate_id)

    async def _process_recruiter_notice(self, item: OutboxItem) -> None:
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        if not slot:
            await self._mark_failed(
                item,
                item.attempts,
                "recruiter_candidate_confirmed_notice",
                "recruiter_candidate_confirmed_notice",
                "slot_mismatch",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        recruiter = await get_recruiter(slot.recruiter_id) if slot.recruiter_id else None
        if recruiter is None or recruiter.tg_chat_id is None:
            await self._mark_failed(
                item,
                item.attempts,
                "recruiter_candidate_confirmed_notice",
                "recruiter_candidate_confirmed_notice",
                "recruiter_chat_missing",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        if await self._has_sent_log(
            "recruiter_candidate_confirmed_notice",
            slot.id,
            item.candidate_tg_id,
        ):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        context = {
            "candidate_name": slot.candidate_fio or str(slot.candidate_tg_id or ""),
            "recruiter_name": recruiter.name or "",
            "dt_local": TemplateProvider.format_local_dt(
                slot.start_utc, recruiter.tz or DEFAULT_TZ
            ),
            "tz_name": recruiter.tz or DEFAULT_TZ,
            "join_link": getattr(recruiter, "telemost_url", "") or "",
        }
        rendered = await self._template_provider.render(
            "recruiter_candidate_confirmed_notice",
            context,
            city_id=getattr(slot, "city_id", None),
        )
        if rendered is None:
            await self._mark_failed(
                item,
                item.attempts,
                "recruiter_candidate_confirmed_notice",
                "recruiter_candidate_confirmed_notice",
                "template_missing",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        attempt = item.attempts + 1
        await self._ensure_log(
            "recruiter_candidate_confirmed_notice",
            item,
            attempt,
            rendered,
            item.candidate_tg_id,
        )

        if self._is_circuit_open():
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="recruiter_candidate_confirmed_notice",
                notification_type="recruiter_candidate_confirmed_notice",
                error="circuit_open",
                rendered=rendered,
                retry_after=self._breaker_remaining(),
                candidate_tg_id=item.candidate_tg_id,
                count_failure=False,
            )
            return

        await self._throttle()
        bot = get_bot()
        try:
            await _send_with_retry(
                bot,
                SendMessage(chat_id=recruiter.tg_chat_id, text=rendered.text),
                correlation_id=f"outbox:{slot.id}:{uuid.uuid4().hex}",
            )
        except TelegramRetryAfter as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="recruiter_candidate_confirmed_notice",
                notification_type="recruiter_candidate_confirmed_notice",
                error=str(exc),
                rendered=rendered,
                retry_after=exc.retry_after,
                candidate_tg_id=item.candidate_tg_id,
            )
            return
        except (TelegramServerError, asyncio.TimeoutError, ClientError) as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="recruiter_candidate_confirmed_notice",
                notification_type="recruiter_candidate_confirmed_notice",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=item.candidate_tg_id,
            )
            return
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="recruiter_candidate_confirmed_notice",
                notification_type="recruiter_candidate_confirmed_notice",
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            "recruiter_candidate_confirmed_notice",
            "recruiter_candidate_confirmed_notice",
            rendered,
            item.candidate_tg_id,
        )
        await record_candidate_confirmed_notice()

    async def _process_interview_reminder(self, item: OutboxItem) -> None:
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        if not slot or (
            item.candidate_tg_id is not None and slot.candidate_tg_id != item.candidate_tg_id
        ):
            await self._mark_failed(
                item,
                item.attempts,
                "slot_reminder:mismatch",
                "slot_reminder:mismatch",
                "slot_mismatch",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        candidate_id = slot.candidate_tg_id
        payload = item.payload or {}
        channel = getattr(item, "messenger_channel", "telegram") or "telegram"
        reminder_raw = payload.get("reminder_kind")
        try:
            reminder_kind = ReminderKind(reminder_raw)
        except (ValueError, TypeError):
            reminder_kind = ReminderKind.CONFIRM_2H

        log_type = f"slot_reminder:{reminder_kind.value}"
        notification_type = log_type

        if await self._has_sent_log(log_type, slot.id, candidate_id):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        recruiter = await get_recruiter(slot.recruiter_id) if slot.recruiter_id else None
        state = await _resolve_candidate_state_for_slot(slot)
        tz = await _resolve_candidate_timezone_for_slot(slot, state=state, recruiter=recruiter)
        labels = slot_local_labels(slot.start_utc, tz)
        meeting_link = _resolve_recruiter_meeting_link(recruiter)
        context = _normalize_format_context({
            "candidate_name": slot.candidate_fio or str(candidate_id or ""),
            "candidate_fio": slot.candidate_fio or str(candidate_id or ""),
            "recruiter_name": recruiter.name if recruiter else "",
            "dt_local": TemplateProvider.format_local_dt(slot.start_utc, tz),
            "tz_name": tz,
            "join_link": meeting_link,
            **labels,
        })
        intro_address_safe, _ = _intro_detail(
            getattr(slot, "intro_address", None),
            fallback=None,
            default=INTRO_ADDRESS_FALLBACK,
        )
        recruiter_contact_fallback = recruiter.name if recruiter else None
        intro_contact_safe, _ = _intro_detail(
            getattr(slot, "intro_contact", None),
            fallback=recruiter_contact_fallback,
            default=INTRO_CONTACT_FALLBACK,
        )
        context.update(
            {
                "intro_address": intro_address_safe,
                "intro_contact": intro_contact_safe,
            }
        )
        if (
            reminder_kind is ReminderKind.INTRO_REMIND_3H
            or (slot.purpose or "").lower() == "intro_day"
        ):
            context.update(
                {
                    "address": intro_address_safe,
                    "city_address": intro_address_safe,
                    "recruiter_contact": intro_contact_safe,
                }
            )

        confirm_map = {
            ReminderKind.CONFIRM_6H: "confirm_6h",
            ReminderKind.CONFIRM_3H: "confirm_3h",
            ReminderKind.CONFIRM_2H: "confirm_2h",
            ReminderKind.REMIND_2H: "confirm_2h",
        }

        if reminder_kind is ReminderKind.INTRO_REMIND_3H:
            template_key = "intro_day_reminder"
            reply_markup = kb_attendance_confirm(slot.id)
        elif reminder_kind is ReminderKind.REMIND_10M:
            template_key = "reminder_10m"
            reply_markup = None
        elif reminder_kind in confirm_map:
            template_key = confirm_map[reminder_kind]
            reply_markup = kb_attendance_confirm(slot.id)
        elif reminder_kind is ReminderKind.REMIND_24H:
            await self._mark_sent(
                item,
                item.attempts + 1,
                log_type,
                notification_type,
                None,
                candidate_id,
            )
            return
        else:
            await self._mark_sent(
                item,
                item.attempts + 1,
                log_type,
                notification_type,
                None,
                candidate_id,
            )
            return

        rendered = await self._template_provider.render(
            template_key, context, city_id=getattr(slot, "candidate_city_id", None)
        )
        if rendered is None:
            await self._mark_failed(
                item,
                item.attempts,
                log_type,
                notification_type,
                "template_missing",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        attempt = item.attempts + 1
        await self._ensure_log(
            log_type,
            item,
            attempt,
            rendered,
            candidate_id,
        )

        if self._is_circuit_open():
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error="circuit_open",
                rendered=rendered,
                retry_after=self._breaker_remaining(),
                candidate_tg_id=candidate_id,
                count_failure=False,
            )
            return

        await self._throttle()
        recipient = candidate_id
        if channel != "telegram":
            recipient = await self._resolve_adapter_recipient(item)
            if recipient is None:
                await self._mark_failed(
                    item,
                    attempt,
                    log_type,
                    notification_type,
                    "recipient_missing",
                    rendered,
                    candidate_tg_id=candidate_id,
                )
                return
            send_result = await self._send_via_messenger_adapter(
                item,
                recipient,
                rendered.text,
                buttons=reply_markup.inline_keyboard if reply_markup else None,
                parse_mode="HTML",
            )
            if not send_result.success:
                await self._schedule_retry(
                    item,
                    attempt=attempt,
                    log_type=log_type,
                    notification_type=notification_type,
                    error=str(send_result.error or "adapter_send_failed"),
                    rendered=rendered,
                    candidate_tg_id=candidate_id,
                )
                return
            await self._mark_sent(
                item,
                attempt,
                log_type,
                notification_type,
                rendered,
                candidate_id,
            )
            await record_slot_reminder_sent(reminder_kind)
            return

        bot = get_bot()
        try:
            await _send_with_retry(
                bot,
                SendMessage(chat_id=candidate_id, text=rendered.text, reply_markup=reply_markup),
                correlation_id=f"outbox:{slot.id}:{uuid.uuid4().hex}",
            )
        except TelegramRetryAfter as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                retry_after=exc.retry_after,
                candidate_tg_id=candidate_id,
            )
            return
        except (TelegramServerError, asyncio.TimeoutError, ClientError) as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except TelegramBadRequest as exc:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                str(exc),
                rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        await self._mark_sent(
            item,
            attempt,
            log_type,
            notification_type,
            rendered,
            candidate_id,
        )

    async def _process_slot_assignment_offer(self, item: OutboxItem) -> None:
        payload = dict(item.payload or {})
        candidate_id = item.candidate_tg_id or payload.get("candidate_tg_id")
        if not candidate_id:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_offer",
                "slot_assignment_offer",
                "candidate_missing",
                None,
                candidate_tg_id=None,
            )
            return

        assignment_id = payload.get("slot_assignment_id")
        tokens = (payload.get("action_tokens") or {})
        confirm_token = tokens.get("confirm")
        reschedule_token = tokens.get("reschedule")
        decline_token = tokens.get("decline")
        if not assignment_id or not confirm_token or not reschedule_token:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_offer",
                "slot_assignment_offer",
                "payload_incomplete",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        start_raw = payload.get("start_utc")
        try:
            start_utc = datetime.fromisoformat(start_raw) if start_raw else None
        except Exception:
            start_utc = None
        if start_utc is None:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_offer",
                "slot_assignment_offer",
                "start_missing",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        candidate_tz = payload.get("candidate_tz") or DEFAULT_TZ
        dt_label = fmt_dt_local(start_utc, candidate_tz)
        recruiter_name = payload.get("recruiter_name") or ""
        city_name = payload.get("city_name") or ""
        comment = payload.get("comment")
        is_alternative = bool(payload.get("is_alternative"))

        title = "🔁 Предлагаем другое время" if is_alternative else "📅 Предлагаем время собеседования"
        text = f"{title}\n🗓 {dt_label}"
        if recruiter_name:
            text += f"\n👤 {escape_html(recruiter_name)}"
        if city_name:
            text += f"\n📍 {escape_html(city_name)}"
        if comment:
            text += f"\n\nКомментарий: {escape_html(str(comment))}"
        if decline_token:
            text += "\n\nПодтвердите, выберите другое время или откажитесь."
        else:
            text += "\n\nПодтвердите или выберите другое время."

        keyboard = kb_slot_assignment_offer(
            int(assignment_id),
            confirm_token=str(confirm_token),
            reschedule_token=str(reschedule_token),
            decline_token=str(decline_token) if decline_token else None,
        )

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await get_bot().send_message(candidate_id, text, reply_markup=keyboard)
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="slot_assignment_offer",
                notification_type="slot_assignment_offer",
                error=str(exc),
                rendered=None,
                candidate_tg_id=candidate_id,
            )
            return

        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )

        try:
            await add_message_log(
                "slot_assignment_offer",
                recipient_type="candidate",
                recipient_id=candidate_id,
                slot_assignment_id=int(assignment_id),
                payload={"slot_id": payload.get("slot_id"), "text": text},
            )
        except Exception:
            logger.exception("Failed to persist message log for slot assignment offer")

        # Update state so free-text handler can capture reschedule input.
        try:
            state_manager = get_state_manager()
            await state_manager.update(
                candidate_id,
                {
                    "slot_assignment_state": "waiting_candidate",
                    "slot_assignment_id": int(assignment_id),
                    "slot_assignment_candidate_tz": candidate_tz,
                },
            )
        except Exception:
            logger.exception("Failed to update candidate state for slot assignment offer")

    async def _process_slot_assignment_reschedule_approved(self, item: OutboxItem) -> None:
        payload = dict(item.payload or {})
        candidate_id = item.candidate_tg_id
        if not candidate_id:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_reschedule_approved",
                "slot_assignment_reschedule_approved",
                "candidate_missing",
                None,
                candidate_tg_id=None,
            )
            return

        start_raw = payload.get("start_utc")
        try:
            start_utc = datetime.fromisoformat(start_raw) if start_raw else None
        except Exception:
            start_utc = None
        if start_utc is None:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_reschedule_approved",
                "slot_assignment_reschedule_approved",
                "start_missing",
                None,
                candidate_tg_id=candidate_id,
            )
            return

        candidate_tz = payload.get("candidate_tz") or DEFAULT_TZ
        dt_label = fmt_dt_local(start_utc, candidate_tz)
        comment = payload.get("comment")

        text = f"✅ Перенос подтверждён.\n🗓 Новое время: {dt_label}"
        if comment:
            text += f"\n\nКомментарий: {escape_html(str(comment))}"

        controls = None
        assignment_id = payload.get("slot_assignment_id")
        if assignment_id:
            try:
                controls = await get_candidate_assignment_controls(
                    candidate_tg_id=int(candidate_id),
                    assignment_id=int(assignment_id),
                )
            except Exception:
                logger.exception(
                    "slot_assignment_reschedule_approved.controls_build_failed",
                    extra={"assignment_id": assignment_id, "candidate_id": candidate_id},
                )
        reply_markup = (
            build_candidate_active_meeting_keyboard(controls)
            if controls is not None
            else None
        )

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await get_bot().send_message(candidate_id, text, reply_markup=reply_markup)
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="slot_assignment_reschedule_approved",
                notification_type="slot_assignment_reschedule_approved",
                error=str(exc),
                rendered=None,
                candidate_tg_id=candidate_id,
            )
            return

        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )

        try:
            await add_message_log(
                "slot_assignment_reschedule_approved",
                recipient_type="candidate",
                recipient_id=candidate_id,
                slot_assignment_id=payload.get("slot_assignment_id"),
                payload={"slot_id": payload.get("slot_id"), "text": text},
            )
        except Exception:
            logger.exception("Failed to persist message log for reschedule approved")

    async def _process_slot_assignment_reschedule_declined(self, item: OutboxItem) -> None:
        payload = dict(item.payload or {})
        candidate_id = item.candidate_tg_id
        if not candidate_id:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_reschedule_declined",
                "slot_assignment_reschedule_declined",
                "candidate_missing",
                None,
                candidate_tg_id=None,
            )
            return

        comment = payload.get("comment")
        text = "⛔️ Запрос на перенос отклонён."
        if comment:
            text += f"\n\nКомментарий: {escape_html(str(comment))}"
        text += "\nЕсли время всё ещё подходит, подтвердите его в предыдущем сообщении."

        attempt = item.attempts + 1
        await self._throttle()
        try:
            await get_bot().send_message(candidate_id, text)
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="slot_assignment_reschedule_declined",
                notification_type="slot_assignment_reschedule_declined",
                error=str(exc),
                rendered=None,
                candidate_tg_id=candidate_id,
            )
            return

        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )

        try:
            await add_message_log(
                "slot_assignment_reschedule_declined",
                recipient_type="candidate",
                recipient_id=candidate_id,
                slot_assignment_id=payload.get("slot_assignment_id"),
                payload={"slot_id": payload.get("slot_id"), "text": text},
            )
        except Exception:
            logger.exception("Failed to persist message log for reschedule declined")

    async def _process_slot_assignment_reschedule_requested(self, item: OutboxItem) -> None:
        payload = dict(item.payload or {})
        recruiter_id = payload.get("recruiter_id")
        recruiter = await get_recruiter(recruiter_id) if recruiter_id else None
        if recruiter is None or recruiter.tg_chat_id is None:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_reschedule_requested",
                "slot_assignment_reschedule_requested",
                "recruiter_chat_missing",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        requested_raw = payload.get("requested_start_utc")
        try:
            requested_utc = datetime.fromisoformat(requested_raw) if requested_raw else None
        except Exception:
            requested_utc = None
        if requested_utc is None:
            await self._mark_failed(
                item,
                item.attempts,
                "slot_assignment_reschedule_requested",
                "slot_assignment_reschedule_requested",
                "start_missing",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        candidate_name = payload.get("candidate_name") or payload.get("candidate_id") or "Кандидат"
        candidate_tz = payload.get("candidate_tz") or recruiter.tz or DEFAULT_TZ
        dt_label = fmt_dt_local(requested_utc, recruiter.tz or candidate_tz or DEFAULT_TZ)
        comment = payload.get("comment")

        text = (
            "🔁 Кандидат запросил другое время\n"
            f"👤 {escape_html(str(candidate_name))}\n"
            f"🗓 {dt_label}\n"
            "Откройте CRM, чтобы подтвердить, предложить другое время или отклонить."
        )
        if comment:
            text += f"\nКомментарий: {escape_html(str(comment))}"

        attempt = item.attempts + 1
        await self._throttle()
        try:
            bot = get_bot()
            # Best effort: attach candidate Test 1 report ("анкета") when present,
            # so recruiter can immediately re-assess context on reschedule.
            attachment_sent = False
            try:
                candidate = None
                candidate_key = payload.get("candidate_id")
                if candidate_key:
                    candidate = await candidate_services.get_user_by_candidate_id(str(candidate_key))
                if candidate is None and item.candidate_tg_id:
                    candidate = await candidate_services.get_user_by_telegram_id(int(item.candidate_tg_id))
                if candidate is not None:
                    reports = _candidate_report_paths(candidate)
                    if reports and hasattr(bot, "send_document"):
                        await bot.send_document(
                            recruiter.tg_chat_id,
                            FSInputFile(str(reports[0])),
                            caption=text,
                        )
                        attachment_sent = True
            except Exception:
                logger.exception("Failed to attach candidate report for reschedule request")

            if not attachment_sent:
                await bot.send_message(recruiter.tg_chat_id, text)
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type="slot_assignment_reschedule_requested",
                notification_type="slot_assignment_reschedule_requested",
                error=str(exc),
                rendered=None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
        )

        try:
            await add_message_log(
                "slot_assignment_reschedule_requested",
                recipient_type="recruiter",
                recipient_id=recruiter.tg_chat_id,
                slot_assignment_id=payload.get("slot_assignment_id"),
                payload={"slot_id": payload.get("slot_id"), "text": text},
            )
        except Exception:
            logger.exception("Failed to persist message log for reschedule requested")

    async def _process_intro_day_invitation(self, item: OutboxItem) -> None:
        """Process intro day invitation - immediate invitation with confirmation

        Uses city-specific template 'intro_day_invitation' which should contain
        personalized information like address, contact person, etc.
        """
        slot = await get_slot(item.booking_id) if item.booking_id is not None else None
        if not slot or (
            item.candidate_tg_id is not None and slot.candidate_tg_id != item.candidate_tg_id
        ):
            await self._mark_failed(
                item,
                item.attempts,
                "intro_day_invitation",
                "intro_day_invitation",
                "slot_mismatch",
                None,
                candidate_tg_id=item.candidate_tg_id,
            )
            return

        candidate_id = slot.candidate_tg_id
        channel = getattr(item, "messenger_channel", "telegram") or "telegram"
        log_type = "intro_day_invitation"
        notification_type = "intro_day_invitation"

        if await self._has_sent_log(log_type, slot.id, candidate_id):
            await update_outbox_entry(
                item.id,
                status="sent",
                attempts=item.attempts,
                next_retry_at=None,
                last_error=None,
            )
            return

        recruiter = await get_recruiter(slot.recruiter_id) if slot.recruiter_id else None
        tz = slot.candidate_tz or DEFAULT_TZ
        labels = slot_local_labels(slot.start_utc, tz)

        # Get city name for template context
        city = None
        city_name = ""
        if slot.candidate_city_id:
            from backend.core.db import async_session
            from backend.domain.models import City
            async with async_session() as session:
                city = await session.get(City, slot.candidate_city_id)
                if city:
                    city_name = getattr(city, "name", "") or getattr(city, "name_plain", "") or ""

        context = {
            "candidate_name": slot.candidate_fio or str(candidate_id or ""),
            "candidate_fio": slot.candidate_fio or str(candidate_id or ""),
            "recruiter_name": recruiter.name if recruiter else "",
            "dt_local": TemplateProvider.format_local_dt(slot.start_utc, tz),
            "tz_name": tz,
            "city_name": city_name,
            "join_link": getattr(recruiter, "telemost_url", "") or "",
            **labels,
        }
        city_intro_address = getattr(city, "intro_address", None) if city else None
        city_contact_name = getattr(city, "contact_name", None) if city else None
        city_contact_phone = getattr(city, "contact_phone", None) if city else None

        recruiter_contact_fallback = recruiter.name if recruiter else None
        # Build city-level contact fallback from contact_name + contact_phone
        city_contact_fallback = None
        if city_contact_name and city_contact_phone:
            city_contact_fallback = f"{city_contact_name}, {city_contact_phone}"
        elif city_contact_name:
            city_contact_fallback = city_contact_name
        elif city_contact_phone:
            city_contact_fallback = city_contact_phone

        intro_address_safe, _ = _intro_detail(
            getattr(slot, "intro_address", None),
            fallback=city_intro_address or city_name,
            default=INTRO_ADDRESS_FALLBACK,
        )
        intro_contact_safe, _ = _intro_detail(
            getattr(slot, "intro_contact", None),
            fallback=city_contact_fallback or recruiter_contact_fallback,
            default=INTRO_CONTACT_FALLBACK,
        )
        context.update(
            {
                "intro_address": intro_address_safe,
                "intro_contact": intro_contact_safe,
                "address": intro_address_safe,
                "city_address": intro_address_safe,
                "recruiter_contact": intro_contact_safe,
                "contact_name": city_contact_name or (recruiter.name if recruiter else ""),
                "contact_phone": city_contact_phone or "",
            }
        )

        # Use custom_message from admin UI when provided (preview = actual text)
        custom_message = (item.payload or {}).get("custom_message")
        if custom_message and str(custom_message).strip():
            from types import SimpleNamespace
            rendered = SimpleNamespace(
                text=str(custom_message).strip(),
                key="intro_day_invitation_custom",
                version=None,
            )
        else:
            # Try to render a city-specific template only when it actually exists to avoid
            # silently downgrading to the generic status message.
            template_key = "intro_day_invitation"
            rendered = await self._template_provider.render(
                template_key, context, city_id=slot.candidate_city_id
            )

            if rendered is None:
                await self._mark_failed(
                    item,
                    item.attempts,
                    log_type,
                    notification_type,
                    "template_missing",
                    None,
                    candidate_tg_id=candidate_id,
                )
                return

        attempt = item.attempts + 1
        await self._ensure_log(
            log_type,
            item,
            attempt,
            rendered,
            candidate_id,
        )

        if self._is_circuit_open():
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error="circuit_open",
                rendered=rendered,
                retry_after=self._breaker_remaining(),
                candidate_tg_id=candidate_id,
                count_failure=False,
            )
            return

        await self._throttle()
        recipient = candidate_id
        if channel != "telegram":
            recipient = await self._resolve_adapter_recipient(item)
            if recipient is None:
                await self._mark_failed(
                    item,
                    attempt,
                    log_type,
                    notification_type,
                    "recipient_missing",
                    rendered,
                    candidate_tg_id=candidate_id,
                )
                return
            send_result = await self._send_via_messenger_adapter(
                item,
                recipient,
                rendered.text,
                buttons=kb_attendance_confirm(slot.id).inline_keyboard,
                parse_mode="HTML",
            )
            if not send_result.success:
                await self._schedule_retry(
                    item,
                    attempt=attempt,
                    log_type=log_type,
                    notification_type=notification_type,
                    error=str(send_result.error or "adapter_send_failed"),
                    rendered=rendered,
                    candidate_tg_id=candidate_id,
                )
                return
            try:
                from backend.domain.candidates.status_service import (
                    set_status_intro_day_scheduled,
                    update_candidate_status_by_candidate_id,
                )

                if candidate_id is not None:
                    await set_status_intro_day_scheduled(candidate_id, force=True)
                elif getattr(slot, "candidate_id", None):
                    await update_candidate_status_by_candidate_id(
                        str(slot.candidate_id),
                        CandidateStatus.INTRO_DAY_SCHEDULED,
                        force=True,
                        session=None,
                    )
            except Exception:
                logger.exception(
                    "Failed to update candidate status to INTRO_DAY_SCHEDULED for candidate %s",
                    candidate_id or getattr(slot, "candidate_id", None),
                )
            await self._mark_sent(
                item,
                attempt,
                log_type,
                notification_type,
                rendered,
                candidate_id,
            )
            return

        bot = get_bot()

        try:
            await _send_with_retry(
                bot,
                SendMessage(
                    chat_id=candidate_id,
                    text=rendered.text,
                    reply_markup=kb_attendance_confirm(slot.id),
                ),
                correlation_id=f"outbox:{slot.id}:{uuid.uuid4().hex}",
            )
        except TelegramRetryAfter as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                retry_after=exc.retry_after,
                candidate_tg_id=candidate_id,
            )
            return
        except (TelegramServerError, asyncio.TimeoutError, ClientError) as exc:
            self._open_circuit()
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except TelegramBadRequest as exc:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                str(exc),
                rendered,
                candidate_tg_id=candidate_id,
            )
            return
        except Exception as exc:
            await self._schedule_retry(
                item,
                attempt=attempt,
                log_type=log_type,
                notification_type=notification_type,
                error=str(exc),
                rendered=rendered,
                candidate_tg_id=candidate_id,
            )
            return

        # Update candidate status to INTRO_DAY_SCHEDULED after successful send
        try:
            from backend.domain.candidates.status_service import (
                set_status_intro_day_scheduled,
                update_candidate_status_by_candidate_id,
            )
            if candidate_id is not None:
                await set_status_intro_day_scheduled(candidate_id, force=True)
            elif getattr(slot, "candidate_id", None):
                await update_candidate_status_by_candidate_id(
                    str(slot.candidate_id),
                    CandidateStatus.INTRO_DAY_SCHEDULED,
                    force=True,
                    session=None,
                )
        except Exception:
            logger.exception("Failed to update candidate status to INTRO_DAY_SCHEDULED for candidate %s", candidate_id or getattr(slot, "candidate_id", None))

        await self._mark_sent(
            item,
            attempt,
            log_type,
            notification_type,
            rendered,
            candidate_id,
        )

    async def _send_reschedule_message(self, snapshot: SlotSnapshot, text: str) -> bool:
        if snapshot.candidate_id is None:
            return False

        def _clear_slot(st: State) -> Tuple[State, None]:
            st["picked_slot_id"] = None
            return st, None

        await _update_candidate_state(snapshot.candidate_id, _clear_slot)

        try:
            await show_recruiter_menu(snapshot.candidate_id, notice=text)
            return True
        except RuntimeError:
            logger.warning("Bot is not configured; cannot show reschedule prompt")
        except Exception:
            logger.exception("Failed to send reschedule prompt to candidate %s", snapshot.candidate_id)
        return False

    async def _mark_candidate_rejected(self, candidate_id: Optional[int]) -> None:
        if candidate_id is None:
            return

        def _mark_rejected(st: State) -> Tuple[State, None]:
            st["flow"] = "rejected"
            st["picked_slot_id"] = None
            st["picked_recruiter_id"] = None
            return st, None

        await _update_candidate_state(candidate_id, _mark_rejected)


    @staticmethod
    def _rendered_components(rendered: Optional[object]) -> Tuple[str, Optional[str], Optional[int]]:
        if rendered is None:
            return "", None, None
        text = getattr(rendered, "text", None)
        key = getattr(rendered, "key", None)
        version = getattr(rendered, "version", None)
        if text is None:
            return str(rendered), None, None
        return str(text), key, version

    async def _ensure_log(
        self,
        log_type: str,
        item: OutboxItem,
        attempt: int,
        rendered: object,
        candidate_tg_id: Optional[int],
    ) -> None:
        rendered_text, template_key, template_version = self._rendered_components(rendered)
        try:
            await add_notification_log(
                log_type,
                item.booking_id or 0,
                candidate_tg_id=candidate_tg_id,
                payload=rendered_text,
                delivery_status="pending",
                attempts=attempt,
                last_error=None,
                overwrite=True,
                template_key=template_key,
                template_version=template_version,
            )
        except IntegrityError:
            logger.debug(
                "notification.log.duplicate",
                extra={"booking_id": item.booking_id, "log_type": log_type, "candidate_tg_id": candidate_tg_id},
            )
        except Exception:
            logger.exception(
                "notification.log.persist_failed",
                extra={"booking_id": item.booking_id, "log_type": log_type, "candidate_tg_id": candidate_tg_id},
            )

    async def _mark_sent(
        self,
        item: OutboxItem,
        attempt: int,
        log_type: str,
        notification_type: str,
        rendered: object,
        candidate_tg_id: Optional[int],
        provider_message_id: str | None = None,
    ) -> None:
        self._last_delivery_error = None
        rendered_text, template_key, template_version = self._rendered_components(rendered)
        await update_outbox_entry(
            item.id,
            status="sent",
            attempts=attempt,
            next_retry_at=None,
            last_error=None,
            failure_class=None,
            failure_code=None,
            provider_message_id=provider_message_id,
            dead_lettered_at=None,
            last_channel_attempted=getattr(item, "messenger_channel", "telegram") or "telegram",
        )
        await mark_messenger_channel_healthy(getattr(item, "messenger_channel", "telegram") or "telegram")
        created = False
        try:
            created = await add_notification_log(
                log_type,
                item.booking_id or 0,
                candidate_tg_id=candidate_tg_id,
                channel=getattr(item, "messenger_channel", "telegram") or "telegram",
                payload=rendered_text,
                delivery_status="sent",
                attempts=attempt,
                attempt_no=attempt,
                last_error=None,
                failure_class=None,
                provider_message_id=provider_message_id,
                next_retry_at=None,
                overwrite=True,
                template_key=template_key,
                template_version=template_version,
            )
        except IntegrityError:
            logger.debug(
                "notification.log.duplicate",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        except Exception:
            logger.exception(
                "notification.log.persist_failed",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        logger.info(
            "notification.worker.sent",
            extra={
                "outbox_id": item.id,
                "booking_id": item.booking_id,
                "candidate_tg_id": candidate_tg_id,
                "notification_type": notification_type,
                "log_type": log_type,
                "attempt": attempt,
                "log_created": created,
            },
        )
        await record_notification_sent(notification_type)

    async def _mark_failed(
        self,
        item: OutboxItem,
        attempt: int,
        log_type: str,
        notification_type: str,
        error: str,
        rendered: Optional[object],
        *,
        candidate_tg_id: Optional[int] = None,
    ) -> None:
        self._last_delivery_error = error
        if error == "telegram_unauthorized":
            self._fatal_error_code = error
            self._fatal_error_at = datetime.now(timezone.utc)
        channel = getattr(item, "messenger_channel", "telegram") or "telegram"
        failure = classify_delivery_failure(channel=channel, error=error)
        rendered_text, template_key, template_version = self._rendered_components(rendered)
        await update_outbox_entry(
            item.id,
            status="dead_letter",
            attempts=max(attempt, item.attempts),
            next_retry_at=None,
            last_error=error,
            failure_class=failure.failure_class,
            failure_code=failure.failure_code,
            dead_lettered_at=datetime.now(timezone.utc),
            last_channel_attempted=channel,
        )
        if failure.degraded_reason:
            await set_messenger_channel_degraded(channel, reason=failure.degraded_reason)
        created = False
        try:
            created = await add_notification_log(
                log_type,
                item.booking_id or 0,
                candidate_tg_id=candidate_tg_id,
                channel=channel,
                payload=rendered_text,
                delivery_status="dead_letter",
                attempts=max(attempt, item.attempts),
                attempt_no=max(attempt, item.attempts),
                last_error=error,
                failure_class=failure.failure_class,
                provider_message_id=getattr(item, "provider_message_id", None),
                next_retry_at=None,
                overwrite=True,
                template_key=template_key,
                template_version=template_version,
            )
        except IntegrityError:
            logger.debug(
                "notification.log.duplicate",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        except Exception:
            logger.exception(
                "notification.log.persist_failed",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        logger.error(
            "notification.worker.failed",
            extra={
                "outbox_id": item.id,
                "booking_id": item.booking_id,
                "candidate_tg_id": candidate_tg_id,
                "notification_type": notification_type,
                "log_type": log_type,
                "attempt": attempt,
                "error": error,
                "log_created": created,
            },
        )
        await record_notification_failed(notification_type)
        if self._broker is not None and self._current_message is not None:
            try:
                await self._broker.to_dlq(self._current_message, reason=error)
            except Exception:
                logger.exception(
                    "notification.worker.dlq_error",
                    extra={"outbox_id": item.id, "message_id": self._current_message.id},
                )

    @staticmethod
    def _fatal_error_code_for_retry(error: str) -> Optional[str]:
        normalized = (error or "").strip().lower()
        if "unauthorized" in normalized:
            return "telegram_unauthorized"
        return None

    async def _schedule_retry(
        self,
        item: OutboxItem,
        *,
        attempt: int,
        log_type: str,
        notification_type: str,
        error: str,
        rendered: Optional[object],
        retry_after: Optional[float] = None,
        candidate_tg_id: Optional[int] = None,
        count_failure: bool = True,
    ) -> None:
        self._last_delivery_error = error
        fatal_error_code = self._fatal_error_code_for_retry(error)
        if fatal_error_code is not None:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                fatal_error_code,
                rendered,
                candidate_tg_id=candidate_tg_id,
            )
            return

        channel = getattr(item, "messenger_channel", "telegram") or "telegram"
        failure = classify_delivery_failure(channel=channel, error=error)
        if failure.failure_class in {"permanent", "misconfiguration"}:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                error,
                rendered,
                candidate_tg_id=candidate_tg_id,
            )
            return

        if attempt >= self._max_attempts:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                error,
                rendered,
                candidate_tg_id=candidate_tg_id,
            )
            return

        delay = self._compute_retry_delay(attempt)
        if retry_after is not None:
            delay = max(delay, float(retry_after))
        delay = self._apply_jitter(delay)
        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

        await update_outbox_entry(
            item.id,
            status="pending",
            attempts=max(attempt, item.attempts),
            next_retry_at=next_retry_at,
            last_error=error,
            failure_class=failure.failure_class,
            failure_code=failure.failure_code,
            dead_lettered_at=None,
            last_channel_attempted=channel,
        )
        text, key, version = self._rendered_components(rendered)
        created = False
        try:
            created = await add_notification_log(
                log_type,
                item.booking_id or 0,
                candidate_tg_id=candidate_tg_id,
                channel=channel,
                payload=text,
                delivery_status="failed",
                attempts=max(attempt, item.attempts),
                attempt_no=max(attempt, item.attempts),
                last_error=error,
                failure_class=failure.failure_class,
                provider_message_id=getattr(item, "provider_message_id", None),
                next_retry_at=next_retry_at,
                overwrite=True,
                template_key=key,
                template_version=version,
            )
        except IntegrityError:
            logger.debug(
                "notification.log.duplicate",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        except Exception:
            logger.exception(
                "notification.log.persist_failed",
                extra={
                    "booking_id": item.booking_id,
                    "log_type": log_type,
                    "candidate_tg_id": candidate_tg_id,
                },
            )
        logger.warning(
            "notification.worker.retry_scheduled",
            extra={
                "outbox_id": item.id,
                "booking_id": item.booking_id,
                "candidate_tg_id": candidate_tg_id,
                "notification_type": notification_type,
                "log_type": log_type,
                "attempt": attempt,
                "error": error,
                "delay_seconds": round(delay, 2),
                "next_retry_at": next_retry_at.isoformat() if next_retry_at else None,
                "log_created": created,
            },
        )
        requeued = await self._enqueue_outbox(
            item.id,
            attempt=max(attempt, item.attempts),
            delay=delay,
        )
        if not requeued:
            await self._mark_failed(
                item,
                attempt,
                log_type,
                notification_type,
                BROKER_UNAVAILABLE_REASON,
                rendered,
                candidate_tg_id=candidate_tg_id,
            )
            if count_failure:
                await record_notification_failed(notification_type)
            return
        if count_failure:
            await record_notification_failed(notification_type)
        await record_send_retry()

    def _compute_retry_delay(self, attempt: int) -> float:
        base = self._retry_base * (2 ** max(0, attempt - 1))
        return float(min(self._retry_max, base))

    def _apply_jitter(self, delay: float) -> float:
        return max(1.0, delay * random.uniform(0.85, 1.15))

    def _compute_poll_backoff(self, previous: float, *, reason: str) -> float:
        min_delay = max(1.0, self._base_poll_interval)
        max_delay = max(min_delay, 5.0)
        base = max(previous, min_delay)
        if reason == "transient":
            return min_delay
        next_delay = base * 1.5
        return min(max(next_delay, min_delay), max_delay)

    async def _throttle(self) -> None:
        if self._token_bucket is None:
            return
        await self._token_bucket.consume()

    def _is_circuit_open(self) -> bool:
        return time.monotonic() < self._breaker_open_until

    def _breaker_remaining(self) -> float:
        remaining = self._breaker_open_until - time.monotonic()
        return max(0.0, remaining)

    def _open_circuit(self) -> None:
        low, high = self._breaker_window
        duration = random.uniform(low, high)
        self._breaker_open_until = max(self._breaker_open_until, time.monotonic() + duration)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(record_circuit_open())
        except RuntimeError:
            pass


class _TokenBucket:
    def __init__(self, rate_per_sec: float, capacity: int) -> None:
        self._rate = max(rate_per_sec, 0.1)
        self._capacity = float(max(1, capacity))
        self._tokens = self._capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: float = 1.0) -> None:
        tokens = max(tokens, 0.0)
        while True:
            wait_time = 0.0
            async with self._lock:
                now = time.monotonic()
                delta = now - self._updated
                if delta > 0:
                    self._tokens = min(self._capacity, self._tokens + delta * self._rate)
                    self._updated = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait_time = deficit / self._rate if self._rate else 0.1
            if wait_time > 0:
                await record_rate_limit_wait(wait_time)
                logger.info(
                    "notification.worker.rate_limit_wait",
                    extra={
                        "wait_seconds": round(wait_time, 4),
                        "rate_per_sec": round(self._rate, 4),
                        "capacity": round(self._capacity, 2),
                    },
                )
            await asyncio.sleep(max(wait_time, 0.05))

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def capacity(self) -> float:
        return self._capacity


def configure_notification_service(service: NotificationService) -> None:
    global _notification_service
    _notification_service = service
    service.start()


def get_notification_service() -> NotificationService:
    if _notification_service is None:
        raise NotificationNotConfigured("Notification service is not configured")
    return _notification_service


def reset_notification_service() -> None:
    """Forget the cached notification service (used between app restarts)."""
    global _notification_service
    _notification_service = None

async def run_scheduled_poll() -> None:
    """Standalone job wrapper to avoid pickling issues with self._scheduler."""
    try:
        svc = get_notification_service()
    except NotificationNotConfigured:
        return
    if svc:
        await svc._scheduled_poll()

__all__ = [
    'NotificationService',
    'configure_notification_service',
    'get_notification_service',
    'reset_notification_service',
    'run_scheduled_poll',
]
