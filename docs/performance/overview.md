# Performance Overview (admin_ui)

Цель этого контура: дать **измеряемую наблюдаемость** и **управляемую деградацию** под нагрузкой, не меняя публичные URL/контракты.

## Компоненты

### 1) Метрики (Prometheus)

Endpoint: `GET /metrics` (по умолчанию **включен** в non-prod, **выключен** в prod).

Управление:
- `METRICS_ENABLED=1|0` (явный флаг всегда имеет приоритет)
- если флаг не задан: `ENVIRONMENT!=production` → включено, `production` → выключено

Ключевые метрики:
- HTTP:
  - `http_requests_total{route,method,status,outcome}`
  - `http_request_duration_seconds_bucket{route,method,status,outcome,le}`
  - `latency_p50_seconds{route,method,status,outcome}` (rolling window, approx)
  - `latency_p95_seconds{route,method,status,outcome}` (rolling window, approx)
  - `latency_p99_seconds{route,method,status,outcome}` (rolling window, approx)
  - `http_inflight_requests`
  - `http_errors_total{route,method,status,outcome}`
- Cache (только когда реально отдали ответ из кэша):
  - `served_from_cache_total{route,backend}` где `backend=microcache|redis`
  - `served_stale_total{route,backend}` (когда DB деградировал и отдали stale)
- DB:
  - `db_queries_total{route,operation}` где `operation=select|insert|update|delete|other`
  - `db_query_duration_seconds_bucket{route,operation,le}`
  - `db_slow_queries_total{route,operation}` (threshold по `DB_SLOW_QUERY_SECONDS`, default `0.2`)
  - per-request (best-effort):
    - `http_db_queries_per_request_bucket{route,outcome,le}`
    - `http_db_query_time_seconds_bucket{route,outcome,le}`
  - Pool:
    - `db_pool_checked_out`
    - `db_pool_size`
    - `db_pool_overflow`
    - `db_pool_acquire_seconds_bucket{route,le}` (best-effort: includes wait under contention)
    - `db_pool_timeouts_total`
    - `db_too_many_connections_total`
  - `db_active_connections` (best-effort, `pg_stat_activity`, иначе `-1`)

`outcome`:
- `success`: не 5xx и не marked as degraded
- `degraded`: запрос обслужен в деградации (DB down) и/или отдали stale cache
- `error`: 5xx без degraded-маркера

### 2) Диагностические headers (non-prod)

Для быстрых проверок кэша:
- `PERF_DIAGNOSTIC_HEADERS=1`
- только `ENVIRONMENT!=production`

Тогда ответы могут включать:
- `X-Cache: HIT|MISS|STALE`

### 3) Degraded mode (DB)

Флаг процесса:
- `app.state.db_available` (watcher + fail-fast при DB/Pool ошибках)

Политика:
- если DB недоступна: большинство запросов short-circuit в `503`
- allowlist (см. `backend/apps/admin_ui/perf/degraded/allowlist.py`):
  - статические ресурсы, `/health`, `/metrics`, SPA
  - горячие read endpoints, которые могут обслужиться из кэша: `/api/profile`, `/api/dashboard/summary`, `/api/dashboard/incoming`, `/api/calendar/events`

### 4) Кэш (hot reads)

Слои:
- microcache: in-process, TTL секунды, без кросс-воркер консистентности
- Redis: best-effort, TTL секунды

Read-through wrapper:
- `backend/apps/admin_ui/perf/cache/readthrough.py`
- ключи централизованы в `backend/apps/admin_ui/perf/cache/keys.py`

Stale policy:
- если запрос marked degraded (DB down) и отдали ответ из кэша → `freshness=stale`
- если `stale_seconds>0` (stale-while-revalidate) и TTL истёк, но значение ещё в stale window → отдаём stale и обновляем в фоне (single-flight)

## Как безопасно добавить новый cached endpoint

1. Определи scoping:
   - shared (одинаковый для всех) или per-principal (admin/recruiter и id)
2. Добавь key builder в `backend/apps/admin_ui/perf/cache/keys.py`.
3. Используй `get_cached` / `set_cached` из `backend/apps/admin_ui/perf/cache/readthrough.py`.
   - для защиты tail latency под нагрузкой можно включить `stale_seconds` (stale-while-revalidate)
4. Если endpoint допускается в degraded-mode, добавь path в allowlist.
5. Добавь тест:
   - разные principals → разные ключи (или явно shared)
