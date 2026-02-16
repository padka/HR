# Quality Scorecard (Local)

Цель этого scorecard: измерять прогресс локальной ветки по 3 метрикам перед переносом в staging/prod.

## 1) UI/UX (0..10)

Формула:

- `task_success_rate` — 30%
- `median_time_to_action` — 25%
- `ui_error_rate` — 20%
- `consistency_accessibility` — 25%

Итог:

`UI_UX = 0.30*task_success_rate + 0.25*median_time_to_action + 0.20*ui_error_rate + 0.25*consistency_accessibility`

Где каждое под-значение нормализуется в диапазон `0..10`.

## 2) Codebase Efficiency (0..10)

Формула:

- `test_stability` — 30%
- `lint_debt` — 20%
- `hotspot_reduction` — 25%
- `build_test_runtime` — 15%
- `modularity_boundaries` — 10%

Итог:

`CODEBASE = 0.30*test_stability + 0.20*lint_debt + 0.25*hotspot_reduction + 0.15*build_test_runtime + 0.10*modularity_boundaries`

## 3) Security (0..10)

Формула:

- `auth_session_hardening` — 35%
- `secret_hygiene` — 25%
- `transport_headers` — 20%
- `auditability_monitoring` — 20%

Итог:

`SECURITY = 0.35*auth_session_hardening + 0.25*secret_hygiene + 0.20*transport_headers + 0.20*auditability_monitoring`

## Data Source / Сбор метрик

Для фиксации baseline и динамики использовать:

- `scripts/quality_snapshot.sh`

Скрипт сохраняет снимок в `.local/quality_snapshot/latest.json`.

## Целевые значения текущего цикла

- `UI/UX >= 8.5`
- `Codebase >= 8.5`
- `Security >= 8.0`
