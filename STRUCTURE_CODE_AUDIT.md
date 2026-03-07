# Structure And Code Audit

## Executive Summary

По структуре и качеству кода система находится в состоянии `functional but drag-heavy`.
Текущий стек в целом выбран рационально:

- backend: FastAPI + SQLAlchemy async + PostgreSQL/Redis
- frontend: React + Vite + TanStack Router/Query + TypeScript
- e2e/unit: Playwright + Vitest

Проблема не в выборе технологий. Проблема в том, как код организован поверх них:

- слишком крупные файлы;
- смешение старых и новых integration paths;
- dev/prod asymmetry;
- слабая модульная граница у нескольких ключевых доменов;
- частичный drift между typed frontend/API и фактическим использованием generic transport.

Текущая оценка:

- stack rationality: `8/10`
- codebase structure: `5/10`
- maintainability trend: `4/10` без целевого рефакторинга

## Repo-Grounded Findings

### Largest structural hotspots

Крупнейшие файлы в активном коде:

- [backend/apps/bot/services.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services.py) — `7540` строк
- [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css) — `8717` строк
- [backend/apps/admin_ui/routers/api.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/api.py) — `4560` строк
- [backend/apps/admin_ui/services/candidates.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates.py) — `3632` строки
- [frontend/app/src/app/routes/app/candidate-detail.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail.tsx) — `2937` строк
- [backend/apps/admin_ui/services/dashboard.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/dashboard.py) — `2251` строка
- [backend/apps/admin_ui/services/slots.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/slots.py) — `1921` строка
- [backend/core/ai/service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/ai/service.py) — `1649` строк
- [backend/domain/repositories.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/repositories.py) — `1582` строки
- [backend/apps/admin_ui/routers/candidates.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidates.py) — `1421` строка

Это уже не “большие файлы”, а operational bottlenecks.

### Technology choices: what is actually good

Рациональные решения, которые не надо переписывать:

- FastAPI для административного/API слоя
- SQLAlchemy async
- PostgreSQL как primary runtime database
- Redis для очередей/кеша/операционного контура
- Vite SPA вместо старого server-rendered frontend path
- TanStack Router/Query для data-heavy UI
- Playwright + Vitest как базовый test stack

Замена этого стека сейчас даст churn, но не снимет основные ограничения.

### Structural debt patterns

#### 1. File-level monoliths dominate behavior

Крупнейшие проблемы сосредоточены не на уровне директорий, а на уровне конкретных файлов.
Это замедляет:

- review scope;
- regression analysis;
- локализацию инцидентов;
- ownership clarity;
- targeted testing.

#### 2. Legacy and new integration paths coexist without a hard boundary

Наиболее заметно это в HH:

- новый direct path: [backend/domain/hh_integration](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/hh_integration)
- старый path: [backend/domain/hh_sync](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/hh_sync)

Оба контура сейчас живут рядом, а не за чётким compatibility boundary.
Это повышает риск semantic drift.

#### 3. Frontend data layer only partially normalized

Несмотря на появление domain services в [frontend/app/src/api/services](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/api/services), по route layer всё ещё много прямого `apiFetch(...)`.

Примеры:

- [frontend/app/src/app/routes/app/city-edit.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/city-edit.tsx)
- [frontend/app/src/app/routes/app/detailization.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/incoming.tsx)
- [frontend/app/src/app/routes/app/incoming.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/incoming.tsx)
- [frontend/app/src/app/routes/app/recruiter-edit.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/recruiter-edit.tsx)
- [frontend/app/src/app/routes/app/candidates.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidates.tsx)

Это значит, что typed boundary ещё не стал обязательным архитектурным правилом.

#### 4. Dev/runtime asymmetry is too high

Есть сильный разрыв между intended runtime и local-dev runtime:

- production target: PostgreSQL + Redis
- local dev фактически часто уходит в SQLite fallback

Факт из кода:

- [backend/core/db.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/db.py) для SQLite использует специальный create/repair path
- это уже полезный fallback, но это же и сигнал, что dev parity с production неполная

Следствие:

- часть дефектов ловится только на Postgres;
- часть behaviour зависит от dialect;
- разработка ускоряется локально, но архитектурный feedback становится менее точным.

#### 5. Startup layer overloaded with operational side effects

[backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py) сейчас сочетает:

- app wiring;
- middleware/session setup;
- health/degraded behavior;
- startup bootstrap;
- periodic background workers;
- route inclusion;
- dev bootstrap data.

Файл уже выполняет роль application kernel, operational bootstrap и partial orchestrator одновременно.

#### 6. Security/session model has historical sentinels leaking into business flow

В [backend/apps/admin_ui/security.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/security.py) admin session хранится как `id=-1`.
Это уже привело к фактическому багу в HH integration lookup.

Вывод:

- sentinel-compatible hacks допустимы как migration bridge,
- но их нельзя оставлять как implicit architectural contract.

#### 7. Theme layer still structurally overloaded

Несмотря на новую разбивку по `tokens/components/pages/mobile/motion`, основной вес всё ещё сидит в:

- [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css)

Это означает, что CSS system ещё не доведён до настоящего source-of-truth layering.

## Code Quality Findings

### Error handling style

В кодовой базе много silent/soft exception swallowing:

- `pass`
- best-effort exception guards
- broad `except Exception`

Это местами оправдано для внешних интеграций, но в aggregate превращается в observability debt.

Наиболее рискованные кластеры:

- [backend/apps/bot/services.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services.py)
- [backend/apps/bot/reminders.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/reminders.py)
- [backend/apps/admin_ui/services/bot_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/bot_service.py)
- [backend/core/ai/service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/ai/service.py)

### Domain concentration

Наиболее перегруженные домены:

- candidates
- slots
- bot conversation/delivery
- admin API aggregation
- dashboard/read models

Здесь код одновременно делает:

- queries
- mutations
- orchestration
- side effects
- serialization shaping
- permission branching

Это главный источник maintainability debt.

## Rationality Of Current Technology Choices

## Keep As-Is

- FastAPI
- SQLAlchemy async
- PostgreSQL
- Redis
- React + Vite
- TanStack Router/Query
- Playwright/Vitest

## Strengthen

- frontend typed API adapters as mandatory boundary
- background jobs contract and structured logging
- modularization of candidates/slots/bot/admin API
- Postgres-first local/staging development path
- CSS layer consolidation

## Reduce Or Isolate

- growth of generic `apiFetch(...)` in route components
- admin sentinel identity assumptions
- parallel HH legacy/direct sync paths without an explicit deprecation plan
- giant startup side-effect blocks in `app.py`
- SQLite as primary “it works on my machine” path for complex flows

## Priority Issue Map

### P0

1. Split [backend/apps/admin_ui/routers/api.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/api.py) into domain routers.
2. Split [backend/apps/admin_ui/services/candidates.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/candidates.py) into `queries / mutations / workflow / presenters`.
3. Split [backend/apps/bot/services.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services.py) by capability slices.
4. Normalize admin principal contract to remove `-1` sentinel dependency from integration code.
5. Make typed frontend service layer mandatory for route pages.

### P1

1. Break [frontend/app/src/app/routes/app/candidate-detail.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail.tsx) into page shell + section modules.
2. Move startup/bootstrap/background wiring out of [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py).
3. Consolidate theme source-of-truth and keep [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css) as import shell.
4. Introduce explicit compatibility boundary for `hh_sync` vs `hh_integration`.
5. Make Postgres-backed local dev the documented default again.

### P2

1. Reduce broad `except Exception` usage in non-integration paths.
2. Add ownership/file-size thresholds to CI or review policy.
3. Normalize service naming and serializer/presenter patterns.
4. Reduce static CSS duplication in legacy admin UI assets.

## Recommended Refactoring Waves

### Wave 1: High-leverage backend decomposition

- split `api.py`
- split `candidates.py`
- split `bot/services.py`
- introduce thin presenters/DTO serializers

Expected impact:

- lower regression radius
- easier route-level RBAC proof
- simpler testing

### Wave 2: Frontend boundary enforcement

- forbid new direct `apiFetch(...)` calls in route files when domain service exists
- move candidate/city/recruiter/template/detailization routes to service adapters
- split `candidate-detail.tsx`, `slots.tsx`, `dashboard.tsx`

Expected impact:

- better typed contracts
- smaller page files
- clearer data ownership

### Wave 3: Runtime and startup cleanup

- extract startup/bootstrap/background registration from `app.py`
- separate dev bootstrap from app bootstrap
- isolate degraded-mode decisions

Expected impact:

- lower startup complexity
- easier diagnostics
- cleaner operational behavior

### Wave 4: Persistence and dev parity

- keep sqlite repair only as fallback, not as preferred dev path
- make postgres dev bootstrap one-command reliable
- add local seeded dataset flow

Expected impact:

- fewer dialect-only surprises
- easier reproduction of production defects

### Wave 5: Legacy path retirement

- decide long-term fate of `hh_sync`
- move old integration path behind explicit compatibility flag
- document deprecation path

Expected impact:

- reduced semantic ambiguity
- lower risk of dual-write drift

## Concrete Next Steps

### Next 7 engineering steps

1. Extract `backend/apps/admin_ui/routers/api.py` city/recruiter/template routes into dedicated router modules.
2. Split `backend/apps/admin_ui/services/candidates.py` into `queries.py`, `workflow.py`, `actions.py`, `presenters.py`.
3. Introduce a lint/review rule: no new route/page/service file above `800` LOC.
4. Move direct `apiFetch(...)` usage out of `city-edit.tsx`, `incoming.tsx`, `recruiter-edit.tsx`, `detailization.tsx`.
5. Extract startup tasks from `backend/apps/admin_ui/app.py` into `bootstrap.py` and `runtime_tasks.py`.
6. Replace admin `-1` sentinel assumptions with explicit `admin principal singleton` helper or normalized persistence contract.
7. Write a deprecation note and compatibility plan for `backend/domain/hh_sync`.

## Bottom Line

Система технологически выбрана правильно.

Основной growth bottleneck сейчас:

- не язык,
- не framework,
- не база,
- а избыточная концентрация поведения в нескольких файлах и отсутствие жёстких архитектурных правил на границах.

Если не менять стек, а последовательно убрать file monoliths, legacy overlap и boundary drift, система резко выиграет в:

- скорости изменений,
- предсказуемости регрессий,
- качестве review,
- тестируемости,
- эксплуатационной устойчивости.

