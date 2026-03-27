# RecruitSmart Core Workflows

## Purpose
Каноническое описание ключевых workflow: candidate portal, slot booking/reschedule, notification outbox, MAX onboarding/linking, HH sync/import и recruiter messenger. Это основной документ для совместной работы backend, frontend, QA, design и analytics.

## Owner
Platform Engineering

## Status
Canonical

## Last Reviewed
2026-03-27

## Source Paths
- `backend/apps/admin_ui/routers/candidate_portal.py`
- `backend/domain/candidates/portal_service.py`
- `backend/apps/admin_ui/routers/api_misc.py`
- `backend/domain/slot_assignment_service.py`
- `backend/domain/repositories.py`
- `backend/apps/bot/services/notification_flow.py`
- `backend/apps/bot/app.py`
- `backend/apps/max_bot/app.py`
- `backend/apps/max_bot/candidate_flow.py`
- `backend/apps/admin_ui/routers/hh_integration.py`
- `backend/apps/admin_api/hh_sync.py`
- `backend/domain/hh_integration/service.py`
- `backend/domain/hh_integration/importer.py`
- `backend/domain/hh_sync/worker.py`
- `backend/apps/bot/recruiter_service.py`
- `backend/apps/admin_ui/services/chat.py`

## Related Diagrams
- [overview.md](./overview.md)
- [runtime-topology.md](./runtime-topology.md)

## Change Policy
Если меняется хотя бы один входной endpoint, status transition, token contract или delivery branch, этот документ обновляется вместе с кодом и тестами. Не описывать здесь устаревшие или экспериментальные маршруты как canonical behavior.

## 1. Candidate Portal
### Sequence
```mermaid
sequenceDiagram
    participant C as "Кандидат"
    participant UI as "frontend/app"
    participant UIAPI as "backend.apps.admin_ui.candidate_portal"
    participant DOM as "backend.domain.candidates.portal_service"
    participant DB as "PostgreSQL"

    C->>UI: Открывает /candidate/start?start=signed_portal_token
    UI->>UIAPI: POST /api/candidate/session/exchange
    UIAPI->>DOM: validate signed token + journey_session_id + session_version
    DOM->>DB: find/create candidate + journey session
    DOM-->>UIAPI: journey payload
    UIAPI-->>UI: candidate portal journey
    UI->>UIAPI: GET /api/candidate/journey
    UIAPI->>DOM: build_candidate_portal_journey() / validate header recovery
    DOM->>DB: read profile / screening / active slot / messages
    DOM-->>UIAPI: full journey state
    UI-->>C: Render cabinet dashboard, next action, slot state and inbox
    C->>UI: Save profile / screening / message
    UI->>UIAPI: POST /profile | /screening/save | /messages
    UIAPI->>DOM: save_candidate_profile / save_screening_draft / create_candidate_portal_message
    DOM->>DB: persist candidate + journey step state + chat message
    DOM-->>UIAPI: updated journey state
```

### Entry Surfaces
- Candidate portal can be opened from signed browser links, MAX `startapp` payloads and Telegram `web_app` buttons.
- HH can now act as the public entry source: `/candidate/start?entry=<signed_hh_entry_token>` resolves the active candidate journey and shows a chooser for `Web`, `MAX` and `Telegram`.
- Browser entry uses the signed portal token directly. MAX mini-app entry uses a separate URL-safe launch token that resolves to the same candidate journey contract.
- The portal token remains the source of truth for browser recovery; native app entry only changes the launch surface, not the journey/session invariants.
- The selected HH entry channel is stored in `CandidateJourneySession.payload_json` as `entry_source`, `last_entry_channel`, `last_entry_channel_selected_at` and `entry_channel_history`. This does not create a second journey or change slot/status invariants.
- The same persistence contract is used when the candidate switches launcher from inside `/candidate/journey`: the cabinet records the new `last_entry_channel` before redirecting to the selected Web/MAX/Telegram launcher.

### Product Contract
- The web cabinet is the primary candidate UX and state surface. MAX, Telegram and future channels only deliver entry packages, reminders and mirrored notifications.
- `/candidate/journey` is a persistent cabinet with dashboard, workflow, tests, schedule, inbox, company materials and candidate-visible feedback. It is no longer framed as a messenger-first stepper.
- Recruiter CRM and candidate cabinet share the same conversation history. Messages written from CRM must appear in the candidate web inbox even if the candidate has no active messenger binding.
- Recruiters can send a unified HH entry package from CRM. If HH does not expose a message-capable negotiation action, the system must return an explicit blocked reason and still expose fallback web/MAX/Telegram launch options.

### State
```mermaid
stateDiagram-v2
    [*] --> Profile
    Profile --> Screening: профиль заполнен
    Screening --> SlotSelection: анкета завершена
    SlotSelection --> Status: слот выбран
    Status --> Status: подтверждение / перенос / отмена
    Status --> [*]: journey closed externally

    state Profile {
        [*] --> InProgress
        InProgress --> Completed: fio/phone/city saved
    }

    state Screening {
        [*] --> InProgress
        InProgress --> Completed: all answers saved
    }
```

### Reliability Contract
- Browser reopen recovery first uses the short-lived HttpOnly resume cookie; if the cookie is missing, the portal may still recover from an explicit header token only for an `active` journey session with matching `session_version`.
- Frontend bootstrap order is fixed: route token -> query `token/start/startapp` -> `window.WebApp.initDataUnsafe.start_param` from MAX Bridge -> stored session token.
- If no bootstrap source is available, the candidate portal returns structured recovery states (`recoverable`, `needs_new_link`, `blocked`) so the UI can explain the next step instead of showing a dead-end 401.
- Invite rotation, relink and explicit security recovery bump `session_version`; stale browser/header tokens must fail closed and emit audit trail.
- External channel delivery failure must not block cabinet access. A fresh browser link remains a valid recovery path whenever the portal public URL is healthy.

## 2. Slot Booking And Reschedule
### Sequence
```mermaid
sequenceDiagram
    participant A as "Админ / рекрутер"
    participant API as "backend.apps.admin_ui.api_misc"
    participant S as "backend.domain.slot_assignment_service"
    participant R as "backend.domain.repositories"
    participant B as "backend.apps.bot.notification_flow"
    participant C as "Кандидат"
    participant DB as "PostgreSQL"

    A->>API: POST /api/candidates/{id}/schedule-slot
    API->>S: create_slot_assignment() or propose_alternative()
    S->>DB: lock slot / assignment rows
    S->>R: add_outbox_notification(slot_assignment_offer | reschedule_requested)
    R->>DB: write outbox pending row
    S-->>API: offer/reschedule result
    API-->>A: JSON success
    B->>R: claim_outbox_batch()
    R->>DB: lock pending outbox rows
    B->>B: render template and pick adapter
    B->>C: send confirmation / reschedule prompt
    B->>DB: update outbox sent/failed/retry
```

### State
```mermaid
stateDiagram-v2
    [*] --> Free
    Free --> Pending: slot reserved / offer sent
    Pending --> Confirmed: candidate confirms
    Pending --> Free: candidate cancels or admin rejects
    Confirmed --> RescheduleRequested: candidate asks for new time
    RescheduleRequested --> Confirmed: alternative approved
    RescheduleRequested --> Free: request declined / slot released
```

## 3. Notification Outbox
### Sequence
```mermaid
sequenceDiagram
    participant D as "Domain service"
    participant R as "backend.domain.repositories"
    participant W as "Notification worker"
    participant REG as "Messenger registry"
    participant REL as "Reliability classifier"
    participant AD as "Telegram / MAX adapter"
    participant DB as "PostgreSQL"

    D->>R: add_outbox_notification()
    R->>DB: insert or reuse pending outbox row
    W->>R: claim_outbox_batch()
    R->>DB: lock pending rows with skip_locked and skip degraded channels
    W->>REG: resolve_adapter_for_candidate()
    REG-->>W: platform adapter
    W->>AD: send_message()
    AD-->>W: success / failure
    W->>REL: classify_delivery_failure(channel, error)
    REL-->>W: transient / permanent / misconfiguration
    W->>R: update_outbox_entry() or mark_outbox_notification_sent()
    R->>DB: persist sent / retry_pending / dead_letter + failure metadata
    W-->>D: observable delivery outcome
```

### State
```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Claimed: claim_outbox_batch
    Claimed --> Sent: provider accepted
    Claimed --> RetryPending: transient failure
    Claimed --> DeadLetter: permanent or misconfiguration
    RetryPending --> Pending: retry window
    DeadLetter --> Pending: explicit requeue after cause removal
    Sent --> [*]
```

### Reliability Contract
- Telegram and MAX are separate observable failure domains; degraded state is stored per channel and surfaced to operators.
- `transient` failures stay retryable, `permanent` failures go directly to `dead_letter`, `misconfiguration` failures both dead-letter the item and mark the channel degraded.
- Explicit requeue does not clear degraded state; operators recover the channel first, then requeue affected dead-letter items.

## 4. MAX Onboarding And Linking
### Sequence
```mermaid
sequenceDiagram
    participant A as "Админ"
    participant UI as "backend.apps.admin_ui.api_misc"
    participant M as "MAX bot"
    participant FLOW as "backend.apps.max_bot.candidate_flow"
    participant DOM as "backend.domain.candidates.portal_service"
    participant C as "Кандидат"
    participant DB as "PostgreSQL"

    A->>UI: POST /candidates/{id}/channels/max-link
    UI->>UI: rotate previous active MAX invite
    UI->>DOM: bump candidate portal session version
    UI->>DOM: build public browser link + MAX-safe mini-app launch token
    UI-->>A: deep_link + mini_app_link + browser_link + invite metadata
    C->>M: Open MAX deep link / startapp payload
    M->>FLOW: process_bot_started()
    FLOW->>DOM: resolve signed portal access token() or invite token
    DOM->>DB: find/create candidate + idempotent/conflict-aware link max_user_id
    FLOW->>DOM: ensure_candidate_portal_session() + sign portal token
    DOM-->>FLOW: linked candidate + portal journey
    FLOW-->>C: Start MAX onboarding / continue portal
```

### Launch Contract
- Candidate-facing MAX messages may include `open_app` and browser link buttons that point to the same signed portal journey.
- `startapp` payload must be MAX-safe and public browser fallback must use a public HTTPS candidate portal URL; loopback or non-HTTPS portal URLs are treated as config errors and are surfaced to operators.
- Telegram and MAX adapters normalize button metadata so the same portal flow can be launched as a native web app or as a browser fallback without changing journey/session semantics.

### Recruiter Control
- `Переотправить ссылку` rotates the active MAX invite, bumps `session_version`, keeps current portal progress and emits a fresh access package.
- `Начать заново` abandons the active journey, creates a new `profile` journey, preserves history/audit trail and blocks restart when the candidate already has a confirmed interview.

### State
```mermaid
stateDiagram-v2
    [*] --> Unlinked
    Unlinked --> InviteIssued: admin creates link
    InviteIssued --> InviteSuperseded: admin rotates link
    InviteIssued --> Linked: candidate opens payload / invite
    InviteIssued --> Conflict: same invite used by другой max_user_id
    Linked --> PortalReady: portal token issued
    Linked --> Linked: same invite same max_user_id
    Unlinked --> PublicPlaceholder: feature flag only
    PublicPlaceholder --> Linked
```

### Reliability Contract
- Only one active MAX invite is canonical per candidate. Rotation supersedes previous invite instead of leaving multiple active links.
- Same invite + same `max_user_id` is idempotent. Same invite + different `max_user_id` is conflict with no duplicate candidate/journey rows.
- `messenger_platform` becomes MAX automatically only when candidate has no existing Telegram identity; otherwise preferred channel is preserved until explicit operator action.

## 5. HH Sync And Import
### Sequence
```mermaid
sequenceDiagram
    participant A as "Админ / n8n"
    participant UI as "backend.apps.admin_ui.hh_integration"
    participant API as "backend.apps.admin_api.hh_sync"
    participant H as "HH.ru"
    participant IMP as "backend.domain.hh_integration.importer"
    participant W as "backend.domain.hh_sync.worker"
    participant DB as "PostgreSQL"

    A->>UI: GET /api/integrations/hh/oauth/authorize
    UI->>H: OAuth authorize URL + state
    H-->>UI: callback code
    UI->>H: exchange code for tokens
    UI->>DB: upsert_hh_connection()
    UI-->>A: connected
    A->>UI: POST import vacancies / negotiations
    UI->>IMP: import_hh_vacancies() / import_hh_negotiations()
    IMP->>DB: upsert vacancy bindings, candidates, resumes, negotiations
    A->>API: POST /api/hh-sync/callback or /resolve-callback
    API->>W: handle_sync_callback() / handle_resolve_callback()
    W->>DB: update candidate sync status + HHSyncLog
    API-->>A: {"ok": true}
```

### State
```mermaid
stateDiagram-v2
    [*] --> Disconnected
    Disconnected --> OAuthPending: authorize request
    OAuthPending --> Active: callback exchanged
    Active --> Active: imports / webhooks / refresh
    Active --> Error: token or webhook failure
    Error --> Active: reauth / retry succeeds
    Active --> [*]: connection removed
```

## 6. Recruiter Messenger
### Sequence
```mermaid
sequenceDiagram
    participant R as "Рекрутер"
    participant TG as "Telegram bot"
    participant RS as "backend.apps.bot.recruiter_service"
    participant CHAT as "backend.apps.admin_ui.services.chat"
    participant REG as "Messenger registry"
    participant AD as "Telegram adapter"
    participant C as "Кандидат"
    participant DB as "PostgreSQL"

    R->>TG: /inbox или rc:* callback
    TG->>RS: show_recruiter_inbox() / handle_recruiter_callback()
    RS->>DB: load waiting candidates / access scope
    RS-->>R: candidate list + action buttons
    R->>TG: compose message / action
    TG->>CHAT: send_chat_message()
    CHAT->>DB: persist ChatMessage and delivery metadata
    CHAT->>REG: resolve adapter for candidate platform
    REG->>AD: send_message()
    AD->>C: deliver reply to candidate
    CHAT->>DB: mark delivery status and retry info
```

### State
```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> InboxOpen: /inbox or callback
    InboxOpen --> CandidateSelected: action button pressed
    CandidateSelected --> Composing: free text captured
    Composing --> Sent: adapter accepted
    Composing --> Failed: delivery error
    Failed --> Composing: retry
    Sent --> Idle
```

## 7. Notes On Canonical Coverage
- Candidate portal and slot flows are intentionally tied to `backend.domain` services, not to UI components.
- Outbox delivery is idempotent by design and must remain observable through retry/failure metadata.
- MAX onboarding and HH sync are separate trust boundaries, even though both produce candidate linking side effects.
- Recruiter messenger should be documented together with chat delivery and scope checks, because the user-facing bot flow and the CRM chat service are coupled.
