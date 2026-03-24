# Regression Register

## Purpose
Зафиксировать стартовые красные кейсы Phase 0 stabilization, их blast radius, test layer и итоговый статус после исправлений.

## Owner
Platform Engineering / QA

## Status
Active

## Last Reviewed
2026-03-25

## Source Paths
- `tests/conftest.py`
- `frontend/app/tests/e2e/ui-cosmetics.spec.ts`
- `frontend/app/tests/e2e/ai-copilot.spec.ts`
- `frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx`
- `frontend/app/src/app/routes/app/candidate-detail/CandidateDetailPage.tsx`

## Related Diagrams
- `docs/qa/critical-flow-catalog.md`
- `docs/architecture/core-workflows.md`

## Change Policy
Обновлять при появлении новой регрессии, изменении severity или закрытии issue. Каждая запись должна иметь owner, affected flow и ближайший regression layer.

| ID | Severity | Owner | Affected flow | Reproduction | Required test layer | Status | Resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RS-P0-001 | P0 | Backend Platform | Backend test isolation / settings cache | `make test-cov` падал order-dependent failure в `tests/test_admin_candidate_schedule_slot.py` | pytest | Resolved | Добавлен autouse reset для `get_settings.cache_clear()` в [`tests/conftest.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/conftest.py) |
| RS-P0-002 | P1 | Frontend Platform | Candidate detail insights drawer | Full e2e не находил стабильный trigger инсайтов и падали drawer-based smoke cases | Playwright + vitest | Resolved | Добавлен явный `candidate-insights-trigger` и wiring drawer open в [`frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx`](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx) и [`frontend/app/src/app/routes/app/candidate-detail/CandidateDetailPage.tsx`](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail/CandidateDetailPage.tsx) |
| RS-P0-003 | P1 | Frontend Platform | AI copilot / interview script drawer flow | Playwright ожидал устаревший UX path без открытого insights drawer | Playwright | Resolved | Обновлены сценарии в [`frontend/app/tests/e2e/ai-copilot.spec.ts`](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/tests/e2e/ai-copilot.spec.ts) и [`frontend/app/tests/e2e/ui-cosmetics.spec.ts`](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/tests/e2e/ui-cosmetics.spec.ts) под текущий контракт |
| RS-P0-004 | P2 | Frontend Platform | Messenger desktop split layout | Playwright использовал устаревший selector `button.messenger-thread-card` и не учитывал empty inbox state | Playwright | Resolved | Тест адаптирован под `.messenger-thread-card[role="button"]` и empty-state branch в [`frontend/app/tests/e2e/ui-cosmetics.spec.ts`](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/tests/e2e/ui-cosmetics.spec.ts) |
| RS-P0-005 | P2 | Platform Docs | Canonical docs drift | Старые root/archive docs смешивались с актуальным source of truth | Markdown review | Resolved | Добавлены [`docs/README.md`](/Users/mikhail/Projects/recruitsmart_admin/docs/README.md) и [`docs/archive/README.md`](/Users/mikhail/Projects/recruitsmart_admin/docs/archive/README.md); route count distinction зафиксирован в [`docs/frontend/route-map.md`](/Users/mikhail/Projects/recruitsmart_admin/docs/frontend/route-map.md) |
