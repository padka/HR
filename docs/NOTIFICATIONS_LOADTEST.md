# Notification Load Testing

This document describes how to run the synthetic load generator for the notification broker
and interpret its output. The script does **not** send real Telegram messages – it publishes
synthetic outbox messages into the broker to verify queue throughput/latency.

## Prerequisites

- Python virtualenv for this repo (`.venv`)
- Redis instance for production-parity tests (start via `docker compose up -d redis_notifications` or reuse CI service container)
- `PYTHONPATH` must include the repository root when calling the script

```bash
PYTHONPATH=. .venv/bin/python scripts/loadtest_notifications.py \
  --broker redis \
  --redis-url redis://localhost:6379/0 \
  --count 500
```

## Usage

```
scripts/loadtest_notifications.py [options]

Options:
  --count N              Number of synthetic notifications to publish (0 = disable)
  --duration SEC         Max duration in seconds (0 = disable, can be combined with --count)
  --broker {memory,redis}
                         Broker backend. `memory` uses the in-process queue.
                         `redis` requires redis-py and a reachable Redis server.
  --redis-url URL        Override Redis URL (falls back to REDIS_URL env variable).
  --poll-interval N      Worker poll interval (defaults to settings).
  --batch-size N         Outbox batch size per poll.
  --rate-limit N         Token bucket rate limit (messages per second).
  --metrics-json PATH    Write summary metrics JSON to PATH (creating directories as needed).
  --metrics-csv PATH     Append summary metrics as CSV row to PATH.
```

## Output

Every run prints a JSON summary to stdout and can optionally store JSON/CSV copies when the
respective flags are supplied. Example output:

```json
{
  "count": 500,
  "target_count": 500,
  "duration_sec": 3.42,
  "duration_limit_sec": 0,
  "avg_publish_sec": 0.00031,
  "max_publish_sec": 0.00141,
  "p95_publish_sec": 0.00085,
  "throughput_per_sec": 146.2,
  "broker": "redis",
  "rate_limit": 50.0,
  "batch_size": 100,
  "poll_interval": 1.0,
  "started_at": "2025-11-13T09:15:00.000000+00:00",
  "finished_at": "2025-11-13T09:15:03.420000+00:00"
}
```

Upload the generated `docs/reliability/*.json` / `.csv` artifacts to your MR when validating
performance changes. The file naming convention is `docs/reliability/<YYYYMMDD>-<description>.json`.

## Recommended scenarios

| Scenario | Command | Expectation |
| --- | --- | --- |
| Dev sanity check (memory) | `PYTHONPATH=. python scripts/loadtest_notifications.py --count 200` | `throughput_per_sec > 1000`, avg publish microseconds |
| Pre-release Redis load test | `PYTHONPATH=. python scripts/loadtest_notifications.py --broker redis --redis-url redis://localhost:6379/0 --count 2000 --rate-limit 50 --metrics-json docs/reliability/<date>-redis.json` | `avg_publish_sec < 0.1`, no connection errors, p95 well below 0.1 |
| Time-bound stress | `PYTHONPATH=. python scripts/loadtest_notifications.py --broker redis --duration 60 --count 0 --rate-limit 100 --metrics-csv docs/reliability/loadtest-history.csv` | `throughput_per_sec close to rate limit`, zero DLQ entries |

**CI baseline:** the workflow runs `scripts/loadtest_notifications.py --broker redis --count 2000 --rate-limit 50`
on every PR. Failing threshold: average publish latency ≥ 0.1 s or non-zero exit code.

## Operational Runbook

1. **Health checks**
   - `GET /health/notifications` now returns rate-limit info (`rate_limit_per_sec`, `worker_concurrency`) and the latest `seconds_since_poll`. Treat values > 30 s as an alert.
   - Watch `watchdog_running` – it must be `true` in production. If it flips to `false`, restart the bot service.
   - Scrape `GET /metrics/notifications` from Prometheus – dashboards/alerts rely on gauges `notification_seconds_since_poll`, `notification_outbox_queue_depth` and the per-type sent/failed counters.

2. **Metrics to monitor**
   - `rate_limit_wait_total` / `rate_limit_wait_seconds`: spikes mean the token bucket is throttling; raise `NOTIFICATION_RATE_LIMIT_PER_SEC`.
   - `poll_backoff_total` with reasons `transient_error` / `fatal_error`.
   - `poll_skipped_total` (reason `inflight` usually indicates the worker pool is saturated – increase `NOTIFICATION_WORKER_CONCURRENCY`).
   - `poll_staleness_seconds`: alert if it stays above 30 s.

3. **Restart procedure**
   - Stop the bot service (`systemctl stop bot` or `pkill -f recruitsmart_admin`).
   - Ensure `notification_service.watchdog_running` is `false`, then start the service and verify `/health/notifications` returns status `ok`.
   - If the queue remains > 0 after restart, bump `NOTIFICATION_RATE_LIMIT_PER_SEC` and/or `NOTIFICATION_WORKER_CONCURRENCY`, deploy, and monitor the rate-limit metrics.
