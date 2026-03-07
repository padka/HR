# PRE-RELEASE WINDOW CHECKLIST (v3)

Дата: 2026-03-01

Ниже перечислены отложенные (неблокирующие для текущего recheck) пункты, которые должны быть закрыты в pre-release окне.

| Item | Owner | Шаги/команды | Критерий приемки | Blocks Prod If Failed |
|---|---|---|---|---|
| Manual sign-off UX (Sprint 1, `manual_pending`) | QA Lead + Product | 1) Пройти чек UX по `/app/slots`, `/app/candidates`, `/app/cities`.<br>2) Зафиксировать протокол sign-off. | Подписанный UX sign-off; нет P1/P0 UX-блокеров. | **Yes** |
| Manual demo sign-off (Sprint 1, `manual_pending`) | Release Captain + Product | 1) Демо цепочки city -> slot -> candidate.<br>2) Протокол демо в release note. | Demo sign-off подписан, сценарий пройден без блокеров. | No |
| Internal security review (Sprint 2, `manual_pending`) | Security Engineer | 1) Провести ручной AppSec review по admin surface.<br>2) Подписать internal review record. | Security review статус `approved`/`accepted_with_actions`. | **Yes** |
| Clean-room docker compose rehearsal | SRE/DevOps | 1) Запустить Docker daemon.<br>2) `docker compose --env-file <prod-like.env> up -d --build postgres redis_notifications redis_cache migrate admin_ui admin_api`.<br>3) Проверить health/readiness и логи. | Все сервисы `healthy`; миграции завершены; нет crash-loop. | **Yes** |
| Full backup/restore drill | DBA + SRE | 1) `pg_dump ... -Fc`.<br>2) `pg_restore` в staging-копию.<br>3) Прогнать smoke (`/health`, `/ready`, candidate CRUD). | Восстановление успешно; целостность данных подтверждена. | **Yes** |
| Canary rollback drill | SRE/DevOps | 1) Выкатить canary (10%).<br>2) Искусственно триггернуть rollback.<br>3) Проверить восстановление SLO. | Rollback укладывается в SLA; health зеленый после отката. | **Yes** |
| Telegram live E2E rehearsal | Integration Engineer | 1) Включить `BOT_ENABLED=true`, валидный `BOT_TOKEN`.<br>2) Назначение встречи -> reminder -> подтверждение/отмена.<br>3) Проверить отсутствие дублей и корректные таймзоны. | Все шаги E2E пройдены, дубли/ошибки отсутствуют. | **Yes** |
| OpenAI live rehearsal (generation flow) | Integration Engineer + Backend | 1) Включить `AI_ENABLED=true`, валидный `OPENAI_API_KEY`.<br>2) 20-50 последовательных генераций интервью-скрипта.<br>3) Зафиксировать timeout/error rate. | Нет бесконечных запросов; error-rate в допустимом диапазоне. | No |
| Production rate-limit backend (Redis) verification | SRE/DevOps | 1) `RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_REDIS_URL` задан.<br>2) Проверить, что нет fallback на in-memory в прод-конфиге. | Логи подтверждают Redis storage для limiter. | **Yes** |

## Примечания
- `manual_pending` из formal gate (`artifacts/recheck_v3/test_results/formal_gate_latest_v3.json`) официально учтен и перенесен сюда.
- Пункты со значением `Blocks Prod If Failed = Yes` должны быть закрыты до финального `GO` sign-off production window.
