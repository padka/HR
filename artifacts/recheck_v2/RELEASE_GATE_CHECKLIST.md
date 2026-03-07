# RELEASE GATE CHECKLIST (recheck v2, post-fix)

Дата: 2026-03-01

| Gate | Статус | Evidence |
|---|---|---|
| Repo recon + service inventory | PASS | `artifacts/recheck_v2/logs/service_inventory_rg.txt` |
| Health/readiness endpoints | PASS | `artifacts/recheck_v2/logs/precheck_health_endpoints.txt`, `artifacts/recheck_v2/ops/health_metrics_v2.txt` |
| Formal gate pack (backend/frontend/e2e) | PASS (`manual_pending`) | `artifacts/recheck_v2/test_results/formal_gate_v2_postfix.log`, `artifacts/recheck_v2/test_results/formal_gate_latest_v2_postfix.json` |
| Backend contract tests (candidate create/schedule) | PASS | `artifacts/recheck_v2/test_results/test_admin_candidate_schedule_slot_postfix.log` |
| Frontend contract tests (candidate-new flow) | PASS | `artifacts/recheck_v2/test_results/candidate_new_ui_postfix.log` |
| API smoke: candidate create-flow (post-fix) | PASS | `artifacts/recheck_v2/logs/api_smoke_candidate_create_contract_postfix_18111.txt` |
| API smoke: schedule-slot without tg | PASS | `artifacts/recheck_v2/logs/api_smoke_schedule_slot_missing_tg_postfix_18111.txt` |
| Migration contract: fail-fast without migration URL | PASS | `artifacts/recheck_v2/ops/migrations_prod_without_migration_url.log` |
| Migration contract: success with migration URL | PASS | `artifacts/recheck_v2/ops/migrations_prod_with_migration_url_hardened.log` |
| Security audit (pip/npm/secrets) | PASS | `artifacts/recheck_v2/security/pip_audit_v2_postfix.txt`, `artifacts/recheck_v2/security/npm_audit_v2_postfix.json`, `artifacts/recheck_v2/security/secret_scan_v2_postfix.log` |
| Perf gate (mixed 600 rps) | PASS | `artifacts/recheck_v2/perf/perf_gate_v2_workers2_pass.log`, `artifacts/recheck_v2/perf/perf_gate_summary_v2_workers2_pass.json`, `artifacts/recheck_v2/perf/perf_gate_v2_workers2_pass.rc` |
| Perf route-latency analyzer (client + metrics merge) | PASS | `scripts/loadtest_profiles/analyze_step.py`, `artifacts/recheck_v2/perf/analyze_step_workers2_reference.json` |
| Integrations (Telegram/OpenAI live checks) | PASS | `artifacts/recheck_v2/ops/telegram_sandbox_v2.json`, `artifacts/recheck_v2/ops/openai_live_json_mode_v2.json`, `artifacts/recheck_v2/ops/openai_admin_endpoint_v2.json` |

## Итог gate
- **OVERALL: PASS**
- Статус после закрытия perf-блокера: all required gates green.

## История (superseded)
- Предыдущий неуспешный perf-run сохранён для ретроспективы:
  - `artifacts/recheck_v2/perf/perf_gate_v2_postfix_18111_tuned_with_serverlog.log`
  - `artifacts/recheck_v2/perf/server_18111_tuned_for_perf.log`
