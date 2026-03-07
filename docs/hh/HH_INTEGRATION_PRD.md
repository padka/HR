# HH Integration PRD

## Problem
Сейчас HH-путь в RecruitSmart реализован как связка `кандидат оставляет ссылку -> n8n пытается найти negotiation -> локальная CRM хранит только несколько hh_* полей на users`. Это решает узкий кейс, но не дает устойчивой идентификации, не поддерживает импорт вакансий и откликов как внешний домен, не обеспечивает нормальный sync lifecycle и плохо масштабируется на реальные recruiter workflows.

## Business goal
Сделать HH полноценным внешним интеграционным доменом, чтобы CRM:
- устойчиво связывала кандидата с `resume / vacancy / negotiation / employer / manager_account`;
- импортировала вакансии, отклики и resume metadata без ручных ссылок;
- позволяла рекрутеру работать в CRM как в primary UI;
- синхронизировала релевантные действия обратно в HH action-first способом;
- была устойчива к дублям, retry, lag, polling gaps и evolving HH states.

## Non-goals
- Не строить full chat mirror на первом этапе.
- Не делать hardcoded HH status table как source of truth.
- Не пытаться синхронизировать каждое локальное поле обратно в HH.
- Не выкидывать сразу существующий `backend/domain/hh_sync`; он остается как legacy compatibility path до миграции на новый модуль.

## Current repo-grounded state
- Legacy integration entrypoints:
  - `backend/apps/admin_api/hh_sync.py`
  - `backend/domain/hh_sync/dispatcher.py`
  - `backend/domain/hh_sync/worker.py`
  - `backend/domain/hh_sync/mapping.py`
- Current persistence is candidate-centric only:
  - `backend/domain/candidates/models.py` -> `hh_resume_id`, `hh_negotiation_id`, `hh_vacancy_id`, `hh_synced_at`, `hh_sync_status`, `hh_sync_error`
  - migration `backend/migrations/versions/0089_add_hh_sync_fields_and_log.py`
- Current orchestration depends on `n8n` webhooks and static mapping from internal statuses to coarse HH targets.
- Current UI only shows HH link/status in candidate detail, but CRM still does not model HH as first-class domain.

## Product requirements

### PR-1. Identity foundation
System MUST persist external HH identities outside of ad-hoc candidate fields:
- connection-level identity for authorized employer/manager account;
- candidate external identity (`resume_id`, `negotiation_id`, `vacancy_id`, employer/manager identifiers);
- vacancy external binding.

### PR-2. OAuth foundation
System MUST support employer OAuth 2.0 with:
- authorization URL generation;
- authorization code exchange;
- refresh token storage;
- encrypted token persistence;
- connection status visibility.

### PR-3. Action-first orchestration
System MUST treat HH transitions as actions, not arbitrary statuses:
- fetch available negotiation actions at runtime;
- execute HH commands against action URLs/arguments;
- persist resulting HH state and local sync outcome.

### PR-4. Hybrid inbound sync
System MUST support webhook-first + polling fallback:
- webhook ingestion for supported HH events;
- idempotent callback storage;
- replay-safe processing;
- scheduled reconciliation for missed events and drift.

### PR-5. Observability and recovery
System MUST expose:
- sync job log;
- webhook delivery log;
- pending/failed/synced state;
- last sync error;
- manual re-sync entrypoints;
- audit trail for inbound/outbound HH operations.

### PR-6. Safe UX contract
UI MUST show:
- source `HH`;
- linked identifiers and deep links;
- external vacancy/negotiation state;
- allowed HH actions only;
- pending/failed sync states;
- conflict banners and manual re-sync controls.

## MVP scope
1. HH employer OAuth.
2. Connection storage with encrypted tokens.
3. Stable webhook receiver with idempotent delivery log.
4. New domain tables for connection / candidate identity / vacancy binding / negotiation snapshot.
5. Admin endpoints to initiate OAuth and inspect connection status.
6. Documentation and contracts for later import/action/reconciliation phases.

## Later scope
- Initial vacancy import.
- Negotiation import.
- Resume snapshot ingestion.
- Action execution from CRM.
- Full inbound/outbound sync lifecycle.
- Conflict UI and admin dashboards.

## Success metrics
- 100% of HH-linked candidates carry stable external identifiers instead of only raw link text.
- Duplicate webhook deliveries do not create duplicate jobs/events.
- OAuth connect flow is deterministic and auditable.
- Existing legacy `hh_sync` remains operational during migration period.

## Acceptance criteria for current tranche
- New HH integration module exists in code and does not break current `hh_sync` flow.
- Admin can generate HH OAuth authorize URL and complete code exchange.
- HH tokens are stored encrypted at rest.
- External webhook receiver records deliveries idempotently and returns `202`/`409` appropriately.
- Foundation models are covered by targeted tests.
