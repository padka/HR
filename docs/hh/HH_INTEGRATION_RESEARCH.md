# HH Integration Research

## Executive finding
HH API already covers the core ATS integration path RecruitSmart needs: OAuth2, employer context, vacancies, resumes, negotiations, actions, templates and webhook notifications. The critical architectural constraint is that HH lifecycle is action-driven, not free-status-driven. RecruitSmart therefore should integrate HH as an external domain with runtime action discovery, versioned mapping and explicit sync recovery.

## Primary sources
- HH OpenAPI / ReDoc: <https://api.hh.ru/openapi/redoc>
- HH OpenAPI spec download: <https://api.hh.ru/openapi/specification/public>

## A. OAuth and auth model
### What it is
HH exposes OAuth2 authorization code flow for user/employer authorization and token exchange via `POST /token`.

### What HH API allows
- Authorization URL: `https://hh.ru/oauth/authorize?...`
- Code exchange: `POST https://api.hh.ru/token`
- Refresh flow via `refresh_token`
- `refresh_token` is one-time use after `access_token` expiry
- `role=employer`, `force_role=true`, `skip_choose_account=true` can be used to streamline employer auth
- `GET /me` returns current profile and auth type
- `GET /manager_accounts/mine` returns available working accounts and current account context

### CRM implication
RecruitSmart should store employer integration as an explicit connection object and attach manager account context to all HH employer calls.

### Limits
- Missing `User-Agent` or `HH-User-Agent` leads to `400`
- Refresh semantics are strict; stale refresh tokens are invalid
- One user can have multiple working manager accounts

### Recommended solution
- Server-side code exchange only
- Encrypted token persistence
- Explicit `manager_account_id`
- Per-connection webhook URL key

### MVP
- Build auth URL
- Exchange code
- Call `/me` and `/manager_accounts/mine`
- Save connection

### Later
- Background token refresh
- Reconnect / revoke UX

## B. Negotiations and lifecycle
### What it is
HH employer workflow is built around negotiations (responses/invitations), collections, employer states and executable actions.

### What HH API allows
- List collection/state descriptors via `GET /negotiations`
- List items in collection via `GET /negotiations/{collection_name}`
- Read specific negotiation via `GET /negotiations/{nid}`
- Execute available action via `PUT /negotiations/{collection_name}/{nid}`
- Create invitation via `POST /negotiations/phone_interview`, but docs recommend using runtime `negotiations_actions[].url` and arguments instead of hardcoding `phone_interview`
- Responses expose `actions[]` and `resulting_employer_state`

### CRM implication
CRM cannot own HH statuses with static mapping. Local recruiter actions must be translated into HH commands after runtime discovery of allowed actions.

### Limits
- Collections are for retrieval, not stable process semantics
- Employer states vary by employer and vacancy
- Different vacancies can have different allowed states/actions

### Recommended solution
- Action-first orchestration layer
- Versioned mapping table, not enum hardcode
- Unknown-state fallback

### MVP
- Store negotiation identifiers and snapshots
- Do not yet execute arbitrary action sync without runtime discovery

### Later
- Full action orchestration from CRM

## C. Resume / vacancy / identity data
### What it is
HH entities needed for CRM linkage are `resume_id`, `vacancy_id`, `topic_id/negotiation_id`, `employer_id`, `manager_id`, `manager_account_id`.

### What HH API allows
- Vacancy lists
- Resume retrieval
- Negotiation history references inside resume-related payloads
- Deep links and metadata for imported profiles

### CRM implication
Candidate should be linked by external IDs, not by user-supplied HH URL. URL remains a convenience field only.

### Limits
- For pair `resume_id + vacancy_id` there can be only one response/invitation
- Resume and vacancy visibility may depend on employer services/permissions

### Recommended solution
- CandidateExternalIdentity table
- ExternalVacancyBinding table
- Snapshot storage + refresh timestamps

### MVP
- Persist identity tables and snapshots

### Later
- Full vacancy import / resume refresh

## D. Webhooks
### What it is
HH provides Webhook API with event subscriptions.

### What HH API allows
- `POST /webhook/subscriptions`
- `GET /webhook/subscriptions`
- callback payload includes `id`, `subscription_id`, `action_type`, `payload`
- events include `NEW_NEGOTIATION_VACANCY`, `NEW_RESPONSE_OR_INVITATION_VACANCY`, `NEGOTIATION_EMPLOYER_STATE_CHANGE`, vacancy events, chat events

### CRM implication
Webhook receiver should be idempotent and treated as best-effort signal, not guaranteed event bus.

### Limits
- Only one URL per application/user subscription set
- Receiver must answer `2xx` or `409` for duplicates
- Duplicate callbacks happen on timeout / connect failure / unexpected status
- HH explicitly says webhooks are not guaranteed delivery
- There is no first-class secret field in subscription create payload; endpoint hardening should use unguessable URL token

### Recommended solution
- Webhook receiver path with per-connection secret key in URL
- Store every delivery in DB
- Hybrid model: webhook + polling reconciliation

### MVP
- Idempotent receiver and raw delivery log

### Later
- Background event processor and reconciliation jobs

## E. Messages / chats
### What it is
Legacy negotiation message methods still exist in spec but are marked deprecated.

### What HH API allows
- Legacy `GET/POST /negotiations/{nid}/messages`
- New chat APIs exist separately

### CRM implication
Do not center MVP on chat synchronization. Use HH for lifecycle sync first.

### Limits
- Docs explicitly warn legacy message methods are deprecated and should be replaced by new chat methods
- chat-related errors include `chat_archived`, `no_invitation`, limits and readiness gaps

### Recommended solution
- Chat sync is not a core MVP requirement
- If needed later, it should be isolated as separate capability, not mixed into core candidate lifecycle

## F. Error model to design for
Relevant documented errors in negotiation / invite flows:
- `already_applied`
- `wrong_state`
- `limit_exceeded`
- `not_enough_purchased_services`
- `chat_archived`
- `no_invitation`
- `archived`
- `resume_deleted`
- `chat_is_not_ready`
- `test_required`

### CRM implication
Every outbound HH command needs:
- idempotency key
- structured error classification
- retry policy by error class
- recruiter-visible failure state

## Best-practice conclusions for RecruitSmart
### Mandatory
- Treat HH as external domain module
- Use action-first sync
- Use webhook + polling hybrid
- Store raw payload snapshots and normalized fields
- Build manual re-sync and sync log from day one

### Desirable
- Auto import vacancies/responses
- Resume refresh and view sync
- Conflict dashboard
- Admin connection health page

### Unsafe on phase 1
- Full bidirectional chat sync
- Static one-table HH status mapping
- Writing arbitrary local field changes back to HH
- Assuming collection names are durable workflow states
