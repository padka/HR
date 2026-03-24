# Master Test Plan

## Header
- Purpose: Единый тест-план для RecruitSmart Admin на Phase 0: стабилизация, регрессия и выпуск релиз-кандидатов без изменения текущей runtime-модели.
- Owner: QA / Release Engineering
- Status: Canonical, P0
- Last Reviewed: 2026-03-25
- Source Paths: `backend/`, `frontend/app/`, `docs/architecture/*`, `docs/data/*`, `docs/security/*`, `backend/tests/`, `frontend/app/tests/`
- Related Diagrams: `docs/qa/critical-flow-catalog.md`, `docs/qa/traceability-matrix.md`, `docs/qa/release-gate-v2.md`
- Change Policy: Обновлять при изменении test surface, критичных flow или release gate. Не использовать archive-доки как source of truth.

## Цель
План фиксирует, какие уровни тестирования считаются обязательными для backend, frontend, интеграций и критичных пользовательских потоков. Источники правды разделяются по доменам:

- HTTP contracts: backend OpenAPI
- data model: `docs/data/*`
- workflows: `docs/architecture/*`
- security: `docs/security/*`

## Объем
Тест-план покрывает текущую архитектуру monolith:

- FastAPI backend
- React SPA в `frontend/app`
- candidate portal
- MAX и Telegram bot runtimes
- scheduling, messaging, HH sync, AI copilot / interview script

## Уровни тестирования
| Уровень | Что проверяет | Примеры | Обязательность |
| --- | --- | --- | --- |
| Static checks | Синтаксис, типы, линтеры, сборка | `make test`, `npm --prefix frontend/app run lint`, `typecheck`, `build:verify` | Обязательно для RC |
| Unit / component | Изолированную логику | backend pytest, frontend unit tests | Обязательно для измененных модулей |
| Integration | DB, очереди, webhook/idempotency, API contracts | PostgreSQL, Redis, internal workflows | Обязательно для high-risk changes |
| Browser / smoke | Критичные пользовательские потоки | dashboard, portal, scheduling, drawer flows | Обязательно для RC |
| Full E2E | Сквозная регрессия перед выпуском | critical flow catalog | Обязательно для release candidate |
| Non-functional | Security, perf smoke, observability | auth, CSRF, rate limiting, logs, alerts | Обязательно для RC и high-risk |

## Стратегия покрытия
- Изменения в backend валидируются сначала на ближайшем уровне pytest, затем через `make test`.
- Изменения в frontend валидируются unit/component тестами, затем `lint`, `typecheck`, `test`, `build:verify`, `test:e2e:smoke`, `test:e2e`.
- Изменения в критичных потоках требуют browser-level подтверждения и traceability к docs.
- При расхождении docs и кода canonical source of truth остается за кодом и выделенными docs domains.

## Минимальный набор команд
```bash
make test
make test-cov
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
npm --prefix frontend/app run test:e2e
```

## Артефакты
- Протоколы запуска тестов
- Список падений и их owner
- Regression register
- Evidence pack для релиз-кандидата

## Критерии приемки
- Все обязательные команды зелёные.
- Для каждого critical flow есть минимум 2 слоя проверки.
- Нет неразмеченных известных регрессий в release candidate.
- Документация не расходится с актуальным code surface по критичным потокам.

