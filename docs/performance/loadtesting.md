# Load Testing (HTTP) for admin_ui

Цель: **диагностика** (knee of curve, деградация, bottlenecks), а не “50k RPS на ноутбуке”.

## Prereqs

1. Поднять сервис локально:

```bash
ENVIRONMENT=development BOT_ENABLED=false \
METRICS_ENABLED=1 PERF_DIAGNOSTIC_HEADERS=1 \
./.venv/bin/uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000
```

2. Убедиться что `/metrics` доступен:

```bash
curl -sS http://127.0.0.1:8000/metrics | head
```

## Профили нагрузки (life-like)

Профили лежат в `scripts/loadtest_profiles/profiles/`:
- `read_heavy.profile`
- `mixed.profile`
- `write_heavy.profile` (controlled; нужен `PERF_CANDIDATE_ID`)

Каждый профиль задаёт веса (%) и набор endpoint’ов. Токен берётся один раз и переиспользуется.

## Workflow: capacity → steady(5m) → spike

### 1) Capacity discovery (knee-of-curve)

```bash
PROFILE_PATH=scripts/loadtest_profiles/profiles/read_heavy.profile \
TARGET_TOTALS="200 400 800 1200 1600" \
DURATION_SECONDS=45 \
./scripts/loadtest_profiles/capacity.sh
```

Артефакты пишутся в `.local/loadtest/profiles/<profile>_<stamp>/capacity/total_<rps>/`:
- `*.json` (autocannon)
- `metrics.txt` (snapshot `/metrics`)
- `step.json` (агрегированный анализ + knee reasons)
- `knee.json` (итог по профилю)

### 2) Steady (5 minutes)

Выберите `TOTAL_RPS` = “последний стабильный” перед knee (из `knee.json`).

```bash
PROFILE_PATH=scripts/loadtest_profiles/profiles/read_heavy.profile \
TOTAL_RPS=800 DURATION_SECONDS=300 \
./scripts/loadtest_profiles/steady.sh
```

### 3) Spike

```bash
PROFILE_PATH=scripts/loadtest_profiles/profiles/read_heavy.profile \
STEADY_RPS=800 STEADY_SECONDS=30 \
SPIKE_RPS=1200 SPIKE_SECONDS=30 \
./scripts/loadtest_profiles/spike.sh
```

## Формальные критерии knee-of-curve

Определение knee (по умолчанию, можно переопределить env):
- `error_rate > 0.5%` (`KNEE_ERROR_RATE_MAX`, default `0.005`)
- `max route latency p95 > 500ms` (`KNEE_LATENCY_P95_MAX_SECONDS`, default `0.5`)
- `max route latency p99 > 1500ms` (`KNEE_LATENCY_P99_MAX_SECONDS`, default `1.5`)
- `db pool acquire p95 > 50ms` (`KNEE_POOL_ACQUIRE_P95_MAX_SECONDS`, default `0.05`)

Критичные маршруты для knee (фиксировано в `analyze_step.py`):
- `/api/profile`
- `/api/dashboard/summary`
- `/api/dashboard/incoming`
- `/api/calendar/events`

## Как читать результаты

1. CLI summary от autocannon:
   - achieved RPS (avg)
   - p50/p90/p99 latency
   - non2xx/errors/timeouts
2. `step.json`:
   - агрегированный error_rate, client_capped
   - max p95/p99 по критичным маршрутам (из `/metrics`)
   - pool acquire p95 (bucket-based)
3. `metrics.txt`:
   - пром-метрики per-route и per-request DB diagnostics

## Cache-miss profiling (DB cost)

Чтобы измерять стоимость DB путей без влияния microcache/Redis (cold-start / expiry / деградации), используйте:

```bash
PERF_CACHE_BYPASS=1 METRICS_ENABLED=1 PERF_DIAGNOSTIC_HEADERS=1 \
./.venv/bin/uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000
```

Для сбора top SQL (sampled, non-prod only):

```bash
DB_PROFILE_ENABLED=1 DB_PROFILE_OUTPUT=.local/perf/sql_profile.json \
DB_PROFILE_SAMPLE_RATE=0.05 DB_PROFILE_FLUSH_SECONDS=10 \
./.venv/bin/uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000
```

## Seeding (чтобы профили были “похожи на жизнь”)

Если в базе мало сущностей, некоторые ветки `/api/dashboard/incoming` и `/api/calendar/events` будут “слишком лёгкими”.
Для наполнения локальной базы используйте:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/seed_incoming_candidates.py --count 200
PYTHONPATH=. ./.venv/bin/python scripts/seed_test_candidates.py
```

## Legacy scripts

Старые скрипты остаются для обратной совместимости:
- `scripts/loadtest_http_mix.sh`
- `scripts/loadtest_http_capacity.sh`
- `scripts/loadtest_http_steady.sh`
- `scripts/loadtest_http_spike.sh`

Для текущего perf-цикла используйте `scripts/loadtest_profiles/*`.
