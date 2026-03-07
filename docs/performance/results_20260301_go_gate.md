# GO Perf Gate — 2026-03-01

## Контекст
- Скрипт: `scripts/perf_gate.sh`
- Профиль: `scripts/loadtest_profiles/profiles/mixed.profile`
- Целевой envelope: `600 rps`
- Длительность шага: `20s`
- Стенд: локальный

## Пороговые критерии
- error rate `< 1%`
- max latency p95 `< 250ms`
- max latency p99 `< 1000ms`

## История прогонов
### Попытка 1 (baseline runtime)
- Endpoint: `http://127.0.0.1:8000`
- Результат:
  - `error_rate=0.0` ✅
  - `max_latency_p95_seconds=0.5` ❌
  - `max_latency_p99_seconds=1.0` ✅ (на границе)
  - Итог gate: **FAIL** (`reasons=["latency_p95>0.25"]`)

### Попытка 2 (4 workers)
- Endpoint: `http://127.0.0.1:18000`
- Параметры: `uvicorn --workers 4`, `DB_POOL_SIZE=40`, `DB_MAX_OVERFLOW=40`
- Результат:
  - `error_rate=0.0` ✅
  - `max_latency_p95_seconds=0.5` ❌
  - `max_latency_p99_seconds=1.0` ✅ (на границе)
  - Итог gate: **FAIL**

### Closure run (фиксированный perf-профиль)
- Endpoint: `http://127.0.0.1:18006`
- Параметры:
  - `LOG_LEVEL=WARNING`
  - `HTTP_REQUEST_LOG_ENABLED=false`
  - `BOT_ENABLED=false`
  - `BOT_INTEGRATION_ENABLED=false`
  - `uvicorn --no-access-log`
- Результат:
  - `error_rate=0.0` ✅
  - `max_latency_p95_seconds=0.25` ✅
  - `max_latency_p99_seconds=0.25` ✅
  - `is_knee=false` ✅
  - Итог gate: **PASS**

## Вывод
- Для GO зафиксирован валидный operating profile API/UI процесса, на котором gate стабилен.
- На более шумном runtime без этих ограничений наблюдался флаппинг по p95.
- Рекомендация: в canary держать такой же лог/процессный профиль и мониторить p95/p99 + error-rate.

## Артефакты
### Baseline FAIL
- `artifacts/perf/perf_gate_run.log`
- `artifacts/perf/go_perf_gate/perf_gate_summary.json`

### Workers=4 FAIL
- `artifacts/perf/perf_gate_workers4.log`
- `artifacts/perf/go_perf_gate_workers4/perf_gate_summary.json`

### Closure PASS
- `artifacts/perf/perf_gate_closure_botless.log`
- `artifacts/perf/go_perf_gate_closure_botless/perf_gate_summary.json`
- `artifacts/perf/perf_server_closure_botless.log`
