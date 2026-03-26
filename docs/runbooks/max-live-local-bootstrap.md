# MAX Live Local Bootstrap

## Purpose
Описать один воспроизводимый локальный путь для запуска Attila Recruiting admin UI, candidate portal и MAX webhook с публичными HTTPS URL через `cloudflared`.

## Owner
Product Platform / Bot Runtime

## Status
Canonical

## Last Reviewed
2026-03-26

## Source Paths
- `/Users/mikhail/Projects/recruitsmart_admin/scripts/dev_max_live.sh`
- `/Users/mikhail/Projects/recruitsmart_admin/Makefile`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/messenger_health.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py`

## Related Diagrams
- `docs/architecture/runtime-topology.md`
- `docs/architecture/core-workflows.md`

## Change Policy
- Не записывать generated public URLs в tracked `.env.local`.
- Не считать live MAX готовым, если health не подтверждает public HTTPS portal и webhook readiness.

## Preconditions
- `cloudflared` установлен и доступен в `PATH`.
- `.env.local` или `.env.local.example` содержит валидный `MAX_BOT_TOKEN`.
- `MAX_BOT_ENABLED=true`.
- По умолчанию локальные порты `8000` и `8010` свободны.
- Если основной dev stack уже запущен, использовать overrides:
  - `DEV_MAX_LIVE_ADMIN_PORT=8001`
  - `DEV_MAX_LIVE_MAX_PORT=8011`

## Bootstrap Flow

1. Запустить `make dev-max-live`.
   - При конфликте портов: `DEV_MAX_LIVE_ADMIN_PORT=8001 DEV_MAX_LIVE_MAX_PORT=8011 make dev-max-live`
2. Дождаться строк:
   - `Attila Recruiting live-local MAX bootstrap is ready.`
   - public `Admin UI`, `Candidate portal`, `MAX webhook`, `MAX link base`
3. Открыть admin UI и войти:
   - `/app/login`
4. Проверить `/api/system/messenger-health` в админке.
5. Открыть карточку кандидата и проверить `/api/candidates/{id}/channel-health`.
6. Выполнить `Переотправить ссылку`.
7. Открыть bot link в MAX и проверить mini app.
8. Выполнить `Начать заново` и убедиться, что кандидат стартует с шага `profile`.

## Expected Health Signals

- `portal.public_ready=true`
- `portal.max_entry_ready=true`
- `portal.token_valid=true`
- `portal.bot_profile_resolved=true`
- `portal.max_link_base_source=env` или `provider`
- `portal.webhook_public_ready=true`
- `portal.subscription_ready=true`

## Operator Truths

- Удаление чата в MAX не сбрасывает состояние кандидата в CRM.
- Retake выполняется только через CRM action `Начать заново` / `POST /api/candidates/{id}/portal/restart`.
- Browser fallback допустим только если `CANDIDATE_PORTAL_PUBLIC_URL` — публичный HTTPS URL.

## Failure Triage

- `portal_public_url_not_https` или `portal_public_url_loopback`
  - candidate portal не готов к live входу, исправить public URL.
- `max_token_invalid`
  - токен отклонён MAX, перевыпустить токен и перезапустить bootstrap.
- `max_profile_unavailable`
  - проверить `GET /me`, сеть и настройки токена.
- `max_bot_link_base_unresolved`
  - задать `MAX_BOT_LINK_BASE` явно или проверить, что профиль бота отдаёт публичный handle.
- `max_webhook_unreachable`
  - webhook URL не public HTTPS, перезапустить bootstrap.
- `max_subscription_not_ready`
  - бот не подписан на текущий webhook URL, проверить health MAX runtime и повторить bootstrap.

## Verification

- `make dev-max-live`
- `curl -f http://127.0.0.1:${DEV_MAX_LIVE_ADMIN_PORT:-8000}/health`
- `curl -f http://127.0.0.1:${DEV_MAX_LIVE_MAX_PORT:-8010}/health`
- recruiter reissue -> candidate opens MAX mini app
- recruiter restart -> candidate проходит путь заново
