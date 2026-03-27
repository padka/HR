# State Flows

## Purpose
Описывает ключевые пользовательские и UI state flows: где state живет, как он меняется, какие запросы/мутации запускаются и что является источником истины.

## Owner
Frontend platform / UI engineering.

## Status
Canonical.

## Last Reviewed
2026-03-27.

## Source Paths
- `frontend/app/src/app/main.tsx`
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/app/routes/app/candidate-detail/*`
- `frontend/app/src/app/routes/candidate/*`
- `frontend/app/src/app/routes/tg-app/*`
- `frontend/app/src/app/components/RoleGuard.tsx`

## Related Diagrams
- `docs/frontend/route-map.md`
- `docs/frontend/screen-inventory.md`

## Change Policy
- Любой новый экран или значимый state transition должен получить описание здесь.
- Если mutation влияет на несколько экранов, фиксируйте invalidate/refetch paths вместе с flow.

## State Ownership Model

| State type | Owner | Source of truth | Examples |
| --- | --- | --- | --- |
| Server state | React Query | Backend API | Candidate detail, slots, dashboard, profile, messenger threads/messages |
| Route state | TanStack Router | URL | `candidateId`, `token`, route selection |
| Local UI state | React component | Component state | Open/close drawers, active tab, filters, modals, draft text |
| Persistent browser state | `localStorage` / session storage / HttpOnly resume cookie | Browser | Theme, Liquid Glass override, persisted filters, candidate portal bootstrap token and short-lived portal resume cookie |
| Shell runtime state | `RootLayout` | `__root.tsx` | Nav mode, unread chat count, mobile sheet state, motion mode |

## Admin Shell Bootstrap

```mermaid
sequenceDiagram
  participant Browser
  participant Root as RootLayout
  participant Profile as useProfile
  participant Router as TanStack Router
  participant Page as Route page

  Browser->>Root: Load /app/*
  Root->>Profile: fetch current principal (unless hidden routes)
  Profile-->>Root: principal + recruiter/admin profile
  Root->>Root: resolve theme, liquid glass, motion, mobile mode
  Root->>Router: render nav + outlet
  Router->>Page: mount route component
  Page->>Page: fetch page-specific server state with React Query
```

### What matters
- `__root.tsx` owns shell, navigation and unread chat polling.
- Page components own their own queries and mutations.
- `RoleGuard` is a page-level gate, not the primary routing mechanism.

## Candidate Detail Flow

```mermaid
sequenceDiagram
  participant User
  participant Page as CandidateDetailPage
  participant DetailQ as useCandidateDetail
  participant ChannelQ as useCandidateChannelHealth
  participant Actions as useCandidateActions
  participant AI as useCandidateAi
  participant Drawer as CandidateDrawer/CandidateChatDrawer
  participant Modal as CandidateModals
  participant Query as queryClient

  User->>Page: Open /app/candidates/$candidateId
  Page->>DetailQ: load detail payload
  Page->>ChannelQ: load Telegram/MAX channel health
  Page->>AI: load AI summary/coach queries
  Page->>Page: build pipeline/tests/view model
  User->>Drawer: open insights/chat/script surfaces
  User->>Actions: reissue access / restart portal journey
  User->>Modal: schedule slot / intro day / reject / report preview
  Modal->>Actions: execute mutation
  Actions-->>Page: success message
  Page->>DetailQ: refetch candidate detail
  Page->>ChannelQ: refetch after MAX invite rotation / delivery change
  Page->>Query: invalidate ['candidates'] list
```

### What matters
- Detail screen keeps the canonical view model inside `CandidateDetailPage`.
- Mutations must invalidate both detail and list views when they affect candidate status.
- Channel-health UI is separate server state and must be invalidated together with MAX invite rotation or relink actions.
- Drawer state is local; server truth remains in `useCandidateDetail`.

## Candidate Portal Start Flow

```mermaid
sequenceDiagram
  participant Browser
  participant Start as CandidateStartPage
  participant Token as portal token/session helpers
  participant API as candidate portal API
  participant Query as queryClient
  participant Journey as CandidateJourneyPage

  Browser->>Start: Open /candidate/start[/token]
  alt hh entry chooser
    Start->>API: GET /api/candidate/entry/resolve?entry=signed_hh_entry_token
    API-->>Start: candidate summary + channel options
    Start->>API: POST /api/candidate/entry/select
    API-->>Start: launcher url for web / MAX / Telegram
  else direct cabinet bootstrap
    Start->>Token: resolve token route -> query -> MAX Bridge start_param -> stored token
    Start->>API: exchangeCandidatePortalToken(token)
    API-->>Start: journey payload
  else resume existing cabinet
    Start->>API: fetchCandidatePortalJourney()
    API-->>Start: journey payload or error
  end
  Start->>Query: cache candidate-portal-journey
  Start->>Journey: navigate to /candidate/journey
```

### What matters
- `/candidate/start` is a bridge, not the main experience.
- When `?entry=` is present, `/candidate/start` becomes an HH chooser, not a direct token exchange screen.
- The HH entry token is durable and is no longer rejected just because the active portal `session_version` changed. Its job is to reopen the chooser and re-issue a fresh launcher for the same candidate journey.
- Fresh MAX/browser entry must win over stale browser storage. If direct token exchange fails, the flow retries journey bootstrap only without the stored token so resume-cookie recovery cannot be poisoned by stale session storage.
- The browser now keeps a separate long-lived candidate entry token in persistent storage. If a direct cabinet token expires on the same device, the start screen recovers by reopening the chooser instead of asking the candidate to request a new recruiter link.
- Candidate portal loads MAX Bridge lazily and only inside candidate routes; browser fallback does not wait indefinitely for bridge bootstrap.
- Candidate portal uses its own CSS bundle and intentionally bypasses the admin shell.

## Candidate Portal Journey Flow

```mermaid
sequenceDiagram
  participant User
  participant Journey as CandidateJourneyPage
  participant Query as useQuery(candidate-portal-journey)
  participant Mut as portal mutations
  participant API as candidate portal API

  User->>Journey: Edit profile / screening / slot / message
  Journey->>Mut: save profile or draft or reservation
  Mut->>API: POST/PATCH action
  API-->>Mut: next journey payload
  Mut->>Query: replace cached journey
  Journey->>User: render updated state
```

### What matters
- Journey screen is now a persistent candidate cabinet, not just a step-by-step portal.
- Each mutation returns a fresh journey snapshot and replaces cache state.
- Cabinet navigation is local UI state; the source of truth stays in the shared journey payload sections: `dashboard`, `journey`, `tests`, `feedback`, `resources`.
- The web inbox is the primary candidate conversation surface. External channels such as MAX or Telegram are delivery adapters and launch surfaces, not the source of truth for the conversation history.
- Screen state must remain recoverable after refresh and after fresh-link entry, even when an older token is still present in browser storage.
- The journey payload includes a durable candidate entry URL so the browser can keep a recovery anchor and route the candidate back to `Web / MAX / Telegram` without recruiter involvement.

## Candidate Cabinet Surface Model

```mermaid
flowchart TD
  JourneyPayload["CandidatePortalJourneyResponse"] --> Dashboard["dashboard"]
  JourneyPayload --> Workflow["journey"]
  JourneyPayload --> Tests["tests"]
  JourneyPayload --> Inbox["messages + journey.inbox"]
  JourneyPayload --> Company["company + resources"]
  JourneyPayload --> Feedback["feedback"]
  Dashboard --> HomeTab["Главная"]
  Workflow --> PathTab["Мой путь"]
  Tests --> TestsTab["Тесты и анкеты"]
  Inbox --> InboxTab["Сообщения"]
  Company --> CompanyTab["О компании"]
  Feedback --> FeedbackTab["Обратная связь"]
```

### What matters
- `/candidate/start` remains the bootstrap bridge; `/candidate/journey` is the actual cabinet.
- Cabinet UX is channel-agnostic: candidate copy should refer to a fresh link from the recruiter, not require a specific messenger.
- Messages written from recruiter CRM must appear in the candidate web inbox even when no external messenger binding exists.
- The cabinet can now expose lightweight launchers for `web`, `MAX` and `Telegram` from the same journey payload. Switching launcher must not create a second candidate flow or split slot/message history.
- Launcher switching from inside the cabinet goes through a session-authenticated mutation first, so `last_entry_channel` is persisted before the browser opens the next launcher.

## System Delivery Flow

```mermaid
sequenceDiagram
  participant User
  participant Page as SystemPage
  participant HealthQ as useQuery(system-messenger-health)
  participant OutboxQ as useQuery(system-outbox-feed)
  participant LogsQ as useQuery(system-notification-logs)
  participant Mut as retryNotification/cancelNotification

  User->>Page: Open /app/system and switch to delivery tab
  Page->>HealthQ: poll Telegram/MAX health snapshot
  Page->>OutboxQ: poll outbox feed with filters
  Page->>LogsQ: poll notification logs with filters
  User->>Mut: retry or cancel outbox item
  Mut-->>Page: success
  Page->>OutboxQ: refetch list
  Page->>HealthQ: next poll reflects queue/degraded changes
```

### What matters
- Delivery tab combines three query surfaces: channel health, outbox feed and notification logs.
- Telegram/MAX cards are operator summary, not source of truth; authoritative delivery state stays in backend outbox/log tables.
- Retry after `dead_letter` is explicit operator action and should be reflected in both outbox row and channel health snapshot.

## Theme And Shell Flow

```mermaid
flowchart LR
  Theme["localStorage theme / TGTheme.apply"] --> DataTheme["documentElement[data-theme]"]
  Glass["localStorage ui:liquidGlassV2"] --> DataUi["documentElement[data-ui='liquid-glass-v2']"]
  DataTheme --> CSS["theme tokens + page CSS"]
  DataUi --> CSS
  CSS --> Shell["RootLayout shell + navigation"]
  Shell --> Pages["route pages"]
```

### What matters
- Theme selection is browser state, not server state.
- Liquid Glass v2 is a UI mode toggle layered on top of the theme.
- Pages read from CSS variables and should not hard-code a second design system.
