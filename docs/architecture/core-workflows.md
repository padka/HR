# RecruitSmart Core Workflows

## Purpose
Каноническое описание ключевых workflow: candidate portal, slot booking/reschedule, notification outbox, MAX onboarding/linking, HH sync/import и recruiter messenger. Это основной документ для совместной работы backend, frontend, QA, design и analytics.

## Owner
Platform Engineering

## Status
Canonical

## Last Reviewed
2026-03-25

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

    C->>UI: Открывает /candidate/start?start=token
    UI->>UIAPI: POST /api/candidate/session/exchange
    UIAPI->>DOM: resolve token -> resolve candidate -> ensure session
    DOM->>DB: find/create candidate + journey session
    DOM-->>UIAPI: journey payload
    UIAPI-->>UI: candidate portal journey
    UI->>UIAPI: GET /api/candidate/journey
    UIAPI->>DOM: build_candidate_portal_journey()
    DOM->>DB: read profile / screening / active slot / messages
    DOM-->>UIAPI: full journey state
    UI-->>C: Render steps, next action and slot state
    C->>UI: Save profile / screening / message
    UI->>UIAPI: POST /profile | /screening/save | /messages
    UIAPI->>DOM: save_candidate_profile / save_screening_draft / create_candidate_portal_message
    DOM->>DB: persist candidate + journey step state + chat message
    DOM-->>UIAPI: updated journey state
```

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
    participant AD as "Telegram / MAX adapter"
    participant DB as "PostgreSQL"

    D->>R: add_outbox_notification()
    R->>DB: insert or reuse pending outbox row
    W->>R: claim_outbox_batch()
    R->>DB: lock pending rows with skip_locked
    W->>REG: resolve_adapter_for_candidate()
    REG-->>W: platform adapter
    W->>AD: send_message()
    AD-->>W: success / failure
    W->>R: update_outbox_entry() or mark_outbox_notification_sent()
    R->>DB: persist sent / failed / next_retry_at
    W-->>D: observable delivery outcome
```

### State
```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Locked: claim_outbox_batch
    Locked --> Sent: provider accepted
    Locked --> Failed: adapter error / retry limit
    Failed --> Pending: reset_outbox_entry / retry window
    Sent --> [*]
```

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
    UI->>UI: generate invite_token + mini_app_link
    UI-->>A: deep_link + mini_app_link
    C->>M: Open MAX deep link / startapp payload
    M->>FLOW: process_bot_started()
    FLOW->>DOM: resolve_candidate_portal_access_token() or invite token
    DOM->>DB: find/create candidate + link max_user_id
    FLOW->>DOM: ensure_candidate_portal_session() + sign portal token
    DOM-->>FLOW: linked candidate + portal journey
    FLOW-->>C: Start MAX onboarding / continue portal
```

### State
```mermaid
stateDiagram-v2
    [*] --> Unlinked
    Unlinked --> InviteIssued: admin creates link
    InviteIssued --> Linked: candidate opens payload / invite
    Linked --> PortalReady: portal token issued
    InviteIssued --> Conflict: token already bound elsewhere
    Unlinked --> CreatedFromMAX: first MAX contact without invite
    CreatedFromMAX --> Linked
```

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
