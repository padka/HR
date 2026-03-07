# READINESS DIFF (baseline -> текущий recheck v2 + closure)

Сравнение:
- baseline: `PRODUCTION_READINESS_REPORT.md` (GO)
- промежуточный recheck: `PRODUCTION_READINESS_REPORT_v2.md` (NO-GO)
- текущий статус после closure: `PRODUCTION_READINESS_REPORT_v2.md` (**GO**)

## 1) Что улучшилось

| Область | Изменение | Evidence |
|---|---|---|
| Candidate intake P1 | Закрыт дефект create-flow (`POST /api/candidates`) | `artifacts/recheck_v2/logs/api_smoke_candidate_create_contract_postfix_18111.txt` |
| Backend regression | Пройдены тесты create-only/create-with-datetime/create-with-telegram | `artifacts/recheck_v2/test_results/test_admin_candidate_schedule_slot_postfix.log` |
| Frontend regression | Пройдены UI тесты двухшагового submit | `artifacts/recheck_v2/test_results/candidate_new_ui_postfix.log` |
| Perf gate P1 | Закрыт блокер latency на mixed `600 rps` | `artifacts/recheck_v2/perf/perf_gate_v2_workers2_pass.log`, `artifacts/recheck_v2/perf/perf_gate_summary_v2_workers2_pass.json` |
| Perf tooling reliability | `analyze_step.py` теперь учитывает client-side latency по всем worker’ам (autocannon) + merge с `/metrics` | `scripts/loadtest_profiles/analyze_step.py`, `artifacts/recheck_v2/perf/analyze_step_workers2_reference.json` |
| Release contract | Зафиксирован worker fan-out (`WEB_CONCURRENCY=2`) для compose/deploy/runbook | `docker-compose.yml`, `.env.example`, `docker-compose.env.example`, `GO_LIVE_RUNBOOK.md` |

## 2) Что осталось / текущие non-blocking пункты

| Приоритет | Пункт | Статус | Evidence |
|---|---|---|---|
| P2 | Manual sign-off в formal gate | Open (non-blocking) | `artifacts/recheck_v2/test_results/formal_gate_latest_v2_postfix.json` |
| P2 | Fresh clean-room compose rehearsal в этом closure-цикле не перепрогонялся | Open (non-blocking) | `artifacts/recheck_v2/logs/recon_summary.txt` |

## 3) Регрессии
- Новых P0/P1 регрессий в closure-цикле не выявлено.

## 4) Изменение решения
- Было: **NO-GO** из-за открытого P1 perf gate.
- Стало: **GO** после успешного rerun perf gate и обновления release-контракта по worker topology.

## 5) Что нужно держать под контролем после релиза
1. Следить за latency/error-rate по canary (`10% -> 50% -> 100%`) с rollback trigger из runbook.
2. Держать `WEB_CONCURRENCY>=2` и не включать perf gate на single-worker как release-решение.
3. Проверять, что rate-limit в production работает через Redis (не memory fallback).
