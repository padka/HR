# Metrics (admin_ui perf)

Цель: быстро видеть **latency/throughput/errors** по маршрутам, состояние пула БД и эффект кэшей, не раздувая кардинальность и не ломая перфоманс.

## Включение/выключение

`METRICS_ENABLED`:
- если переменная **не задана**: метрики включены по умолчанию в non-prod (`ENVIRONMENT!=production`)
- если задана: `1/true/yes/on` → включено, иначе выключено

`PERF_DIAGNOSTIC_HEADERS=1` (только non-prod):
- добавляет `X-Cache: HIT|MISS|STALE` на ответы (best-effort)

## HTTP

Рекомендуемые метрики:
- `http_requests_total{route,method,status,outcome}`
- `http_request_duration_seconds_bucket{route,method,status,outcome,le}`
- rolling quantiles (approx):
  - `latency_p50_seconds{route,method,status,outcome}`
  - `latency_p95_seconds{route,method,status,outcome}`
  - `latency_p99_seconds{route,method,status,outcome}`
- `http_inflight_requests`
- `http_errors_total{route,method,status,outcome}`

`outcome`:
- `success`: не 5xx и не marked degraded
- `degraded`: запрос обслужен в деградации (DB down) и/или отдали stale cache
- `error`: 5xx (или client disconnect как `499` для метрик)

Кардинальность:
- `route` должен быть **template-like** (например `/api/candidates/{id}`), не raw path.

## Cache

Счётчики (только когда действительно был HIT/STALE):
- `served_from_cache_total{route,backend}` где `backend=microcache|redis`
- `served_stale_total{route,backend}` (stale при деградации DB или SWR stale window)

Диагностика (non-prod):
- `X-Cache: HIT|MISS|STALE`

## DB / SQLAlchemy

Per-query (best-effort, gated by `METRICS_ENABLED`):
- `db_queries_total{route,operation}` где `operation=select|insert|update|delete|other`
- `db_query_duration_seconds_bucket{route,operation,le}`
- `db_slow_queries_total{route,operation}` (`DB_SLOW_QUERY_SECONDS`, default `0.2`)

Per-request (best-effort, на основе request context):
- `http_db_queries_per_request_bucket{route,outcome,le}`
- `http_db_query_time_seconds_bucket{route,outcome,le}`

Pool:
- `db_pool_checked_out`
- `db_pool_size`
- `db_pool_overflow`
- `db_pool_acquire_seconds_bucket{route,le}` (wait/creation under contention)
- `db_pool_timeouts_total`
- `db_too_many_connections_total`

Postgres (best-effort):
- `db_active_connections` (через `pg_stat_activity`, иначе `-1`)

## Overhead/безопасность

Принципы:
- никаких user_id / PII в labels
- метрики по умолчанию выключены в production (если не включать явно)
- если видите, что `METRICS_ENABLED=1` заметно режет throughput: добавляйте sampling для per-query телеметрии (оставляя per-request агрегаты)

