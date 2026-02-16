# Load Testing (HTTP) for admin_ui

Цель: **диагностика** (knee of curve, деградация, bottlenecks), а не “50k RPS на ноутбуке”.

## Prereqs

1. Поднять сервис локально:

```bash
uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000
```

2. Включить метрики (рекомендовано):

```bash
export METRICS_ENABLED=1
export PERF_DIAGNOSTIC_HEADERS=1
```

3. Убедиться что `/metrics` доступен:

```bash
curl -sS http://127.0.0.1:8000/metrics | head
```

## Profiles

### 1) Mixed (single run)

Скрипт: `scripts/loadtest_http_mix.sh`

```bash
BASE_URL=http://127.0.0.1:8000 \
ADMIN_USER=admin ADMIN_PASSWORD=admin \
DURATION_SECONDS=60 \
./scripts/loadtest_http_mix.sh
```

Поддерживает отключение отдельных endpoint’ов через `RATE_*=0`.

### 2) Capacity discovery (ramp)

Скрипт: `scripts/loadtest_http_capacity.sh`

```bash
TARGET_TOTALS="1000 2000 5000 8000 12000" \
DURATION_SECONDS=60 \
./scripts/loadtest_http_capacity.sh
```

Идея: найти точку перелома (рост p95/p99 + non2xx/timeouts).

### 3) Steady (5 minutes)

Скрипт: `scripts/loadtest_http_steady.sh`

```bash
TOTAL_RPS=2000 \
DURATION_SECONDS=300 \
./scripts/loadtest_http_steady.sh
```

### 4) Spike

Скрипт: `scripts/loadtest_http_spike.sh`

```bash
STEADY_RPS=2000 STEADY_SECONDS=30 \
SPIKE_RPS=6000 SPIKE_SECONDS=15 \
./scripts/loadtest_http_spike.sh
```

## Как читать результаты

Скрипты пишут JSON отчеты autocannon в `.local/loadtest/...` и печатают сводку:
- achieved RPS (avg)
- latency p50/p90/p99
- non2xx/errors/timeouts

## Что смотреть в метриках

HTTP:
- `latency_p95_seconds{route="/api/dashboard/summary"}` (rolling window)
- `http_requests_total{outcome="degraded"}`: сколько деградированных ответов

Cache:
- `served_from_cache_total{route="/api/profile",backend="microcache"}`
- `served_stale_total{route="/api/profile",backend="redis"}`

DB:
- `db_pool_checked_out` + `db_pool_overflow` (приближаемся к лимитам пула)
- `db_pool_timeouts_total` (pool exhaustion)
- `db_query_duration_seconds` и `db_queries_total` для поиска N+1 и тяжелых запросов

## Типовой workflow диагностики

1. Прогон `capacity` до появления деградации.
2. Фиксируем “knee of curve”: на каком total p95/p99 растет нелинейно.
3. Смотрим:
   - pool timeouts / too many connections
   - рост `db_queries_total` на один HTTP (N+1)
   - рост `served_stale_total` (ответы начали держаться только на кэше)
4. Дальше оптимизации строго по порядку:
   1. убрать N+1 / selectinload / батчинг
   2. уменьшить payload
   3. индексы
   4. предрасчёт
   5. кэш как усилитель

