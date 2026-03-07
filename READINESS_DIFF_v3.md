# READINESS DIFF v3 (vs v2)

Дата сравнения: 2026-03-01
Базовый документ: `PRODUCTION_READINESS_REPORT_v2.md`
Текущий документ: `PRODUCTION_READINESS_REPORT_v3.md`

## 1) Итог изменения статуса
- **v2:** GO.
- **v3:** **CONDITIONAL GO**.
- **Причина изменения формулировки:** в v3 повторно подтверждены функциональные и perf/security gates, но часть release-операций помечена `SKIPPED` в этом цикле (compose clean-room, live Telegram/OpenAI).

## 2) Что улучшилось
| Область | v2 | v3 | Evidence |
|---|---|---|---|
| Perf gate mixed 600 rps на multi-worker | PASS | PASS (повторно подтверждено) | `artifacts/recheck_v3/perf/perf_gate_summary_v3_workers2_pass.json` |
| Подтверждение `WEB_CONCURRENCY>=2` в runtime topology | Было декларировано | Подтверждено процессами/портами | `artifacts/recheck_v3/logs/worker_topology_v3.txt` |
| Доп. perf профиль | Limited | Добавлен `read-heavy` short profile | `artifacts/recheck_v3/perf/read_heavy_short_v3_step.json` |
| Critical smoke (create/schedule/reschedule/search/kanban move) | Частично | Прогнан end-to-end | `artifacts/recheck_v3/smoke/critical_flow_smoke_v3.json` |
| UI evidence | Ограниченно | Добавлены фактические screenshots | `artifacts/recheck_v3/smoke/ui_candidates_list_v3.png`, `artifacts/recheck_v3/smoke/ui_candidates_kanban_v3.png` |

## 3) Что осталось без изменений
| Область | Статус |
|---|---|
| Formal gate содержит `manual_pending` | Без изменений (не блокер) |
| Security dependency posture (pip/npm) | High/Critical = 0 |
| Основной perf envelope 600 rps | Выполняется при workers >= 2 |

## 4) Новые/измененные риски
| Риск | v2 | v3 | Комментарий |
|---|---|---|---|
| Clean-room compose rehearsal | Untested/Medium | SKIPPED/High (в текущей среде) | Docker daemon недоступен в recheck окружении |
| Live Telegram/OpenAI rehearsal | Pass в v2 artifacts | SKIPPED в v3 env | В v3 runtime bot/AI выключены для локального recheck |
| CSRF behavior in dev/local | Не акцентировалось | Зафиксирован как P2 nuance | Ожидаемое поведение, не production bypass |

## 5) Закрытые / не закрытые пункты
### Закрытые (подтверждены повторно)
- Perf gate multi-worker (`mixed 600 rps`).
- Backend contract/domain/concurrency suites.
- Frontend lint/typecheck/unit + e2e smoke.
- Security baseline (secrets, pip-audit, npm audit).

### Остались к pre-release window
- Manual UX/demo/security sign-off (`manual_pending`).
- Clean-room compose rehearsal.
- Full backup/restore drill.
- Canary rollback drill.
- Live Telegram/OpenAI rehearsal.

См. `PRE_RELEASE_WINDOW_CHECKLIST.md`.

## 6) Вывод
- С инженерной точки зрения core gates (functional/perf/security) в v3 — **зелёные**.
- Для финального production sign-off нужно закрыть pre-release window пункты с флагом `Blocks Prod If Failed = Yes`.
