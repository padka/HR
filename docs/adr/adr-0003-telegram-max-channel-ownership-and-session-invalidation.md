# ADR-0003: Telegram/MAX Channel Ownership And Session Invalidation

## Status
Accepted

## Date
2026-03-25

## Context

До reliability tranche Telegram/MAX linking опирался на invite token и MAX start flow, но два поведения оставались недостаточно детерминированными:

- новый MAX invite мог сосуществовать со старым и не делал предыдущую ссылку явно superseded;
- portal/header recovery зависел от signed portal token, но не имел отдельной `session_version`, которая бы инвалидировала stale browser state после relink или security action;
- `messenger_platform` мог молча дрейфовать при MAX entry, даже если кандидат уже имел установленную Telegram identity;
- outbox delivery не разделял Telegram/MAX как отдельные failure domains с persisted degraded state.

Это создавало риск конфликтной привязки, неочевидного preferred channel и нечёткой operator recovery semantics.

## Decision

1. Telegram и MAX считаются отдельными observable failure domains.
2. Для MAX действует policy: один active invite на кандидата и канал. Новая выдача invite supersede'ит предыдущий active invite.
3. Invite reuse с тем же `max_user_id` считается идемпотентным. Reuse с другим `max_user_id` считается conflict и не должен создавать duplicate side effects.
4. `messenger_platform` не перезаписывается молча при каждом MAX входе. Preferred channel меняется автоматически только если у кандидата ещё нет связанного канала; в остальных случаях требуется явное operator action.
5. `candidate_journey_sessions.session_version` становится частью signed portal token и header recovery contract. Rotation, relink и security recovery инкрементируют версию и инвалидируют stale browser/header sessions.
6. Delivery failures классифицируются как `transient`, `permanent`, `misconfiguration`. `misconfiguration` переводит конкретный канал в degraded state и требует явного operator requeue после устранения причины.

## Consequences

### Positive
- linking/session lifecycle становится auditable и детерминированным;
- operator UI может опираться на per-channel delivery state и degraded snapshot;
- stale portal state перестаёт “магически” восстанавливаться после смены ownership;
- Telegram и MAX не блокируют друг друга при channel-specific деградации.

### Tradeoffs
- появляется дополнительная operational сущность: `session_version`;
- support/runbooks должны различать `superseded invite`, `conflict`, `dead_letter`, `degraded channel`;
- часть старых public MAX assumptions становится historical и не должна считаться canonical production path.

## Implementation Notes

- Schema baseline: `backend/migrations/versions/0098_tg_max_reliability_foundation.py`
- Portal/session contract: `backend/domain/candidates/portal_service.py`
- MAX linking contract: `backend/apps/max_bot/candidate_flow.py`
- Admin operator surfaces: `backend/apps/admin_ui/routers/api_misc.py`, `frontend/app/src/app/routes/app/candidate-detail/CandidateActions.tsx`, `frontend/app/src/app/routes/app/system.tsx`
- Channel degraded state: `backend/core/messenger/channel_state.py`
