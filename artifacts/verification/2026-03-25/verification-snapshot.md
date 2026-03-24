# Verification Snapshot

## Purpose
Единый verification snapshot для RecruitSmart Professionalization Program, Phase 0 stabilization. Файл фиксирует точные команды, итоги прогонов и остаточные наблюдения после закрытия baseline.

## Owner
Platform Engineering / QA

## Status
Green

## Last Reviewed
2026-03-25

## Source Paths
- `Makefile`
- `frontend/app/package.json`
- `tests/conftest.py`
- `frontend/app/tests/e2e/*`

## Related Diagrams
- `docs/qa/release-gate-v2.md`
- `docs/qa/master-test-plan.md`
- `artifacts/verification/2026-03-25/regression-register.md`

## Change Policy
Обновлять только после нового полного baseline run. Если какой-то command set меняется, сначала обновлять canonical QA docs, затем этот snapshot.

## Commands And Results
| Command | Result | Evidence |
| --- | --- | --- |
| `make test` | Green | `923 passed, 2 skipped, 108 warnings in 296.82s (0:04:56)` |
| `make test-cov` | Green | `923 passed, 2 skipped, 110 warnings in 376.23s (0:06:16)`; total coverage `59%` |
| `npm --prefix frontend/app run lint` | Green | exit code `0` |
| `npm --prefix frontend/app run typecheck` | Green | exit code `0` |
| `npm --prefix frontend/app run test` | Green | `15 files, 55 tests passed` |
| `npm --prefix frontend/app run build:verify` | Green | production build OK; `Bundle budgets: OK` |
| `npm --prefix frontend/app run test:e2e:smoke` | Green | `11 passed (15.8s)` |
| `npm --prefix frontend/app run test:e2e` | Green | `57 passed (1.1m)` |

## Stabilization Evidence
- Targeted `ui-cosmetics.spec.ts` rerun after fixes: `12 passed (17.4s)`.
- Полный e2e подтвердил закрытие исходно красных зон:
  - `a11y: /app/dashboard has no critical violations`
  - `AI Copilot can generate summary and insert reply draft`
  - `candidate details drawer scrolls through insights`
  - `candidate detail opens interview script panel from insights drawer`
  - `messenger desktop keeps split layout visible`

## Observations
- Full Playwright runs поднимают `admin_ui` в test sqlite режиме и логируют `Automatic schema upgrade skipped` для SQLite-specific `ALTER TABLE ... TYPE`; это ожидаемая non-blocking деградация test bootstrap, не production signal.
- Backend suites продолжают выдавать существующие предупреждения:
  - Pydantic protected namespace warning для `model_custom_emoji_id`
  - Python 3.12+ sqlite datetime adapter deprecation
  - отдельные `ResourceWarning` на незакрытые sqlite connections в тестах
- Full e2e логирует долгие `candidate-chat/threads/updates` long-poll requests около 25s; это соответствует текущему polling-contract и не привело к падениям.

## Gate Decision
- Release Gate v2: green for current baseline.
- Known red tests: none.
- Open release blockers: none.
