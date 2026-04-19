# State Flows

## Purpose
Описывает ключевые пользовательские и UI state flows для текущего supported frontend runtime.

Важно:
- legacy candidate portal implementation не является supported mounted runtime surface;
- future standalone candidate web flow остаётся target state, но не описывается здесь как live route contract;
- bounded MAX mini-app at `/miniapp` уже смонтирован и описывается здесь как guarded controlled-pilot flow;
- full MAX runtime/channel rollout beyond the bounded pilot остаётся target state и не описывается здесь как production live contract.

## Owner
Frontend platform / UI engineering

## Status
Canonical

## Last Reviewed
2026-04-19

## Source Paths
- `frontend/app/src/app/main.tsx`
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/app/routes/app/candidate-detail/*`
- `frontend/app/src/app/routes/miniapp/*`
- `frontend/app/src/app/routes/tg-app/*`
- `backend/apps/admin_api/max_launch.py`
- `backend/apps/admin_api/candidate_access/router.py`
- `frontend/app/src/app/components/RoleGuard.tsx`

## Related Docs
- `docs/frontend/route-map.md`
- `docs/frontend/screen-inventory.md`

## State Ownership Model

| State type | Owner | Source of truth | Examples |
| --- | --- | --- | --- |
| Server state | React Query | Backend API | Candidate detail, slots, dashboard, profile, messenger threads/messages |
| Route state | TanStack Router | URL | `candidateId`, route selection |
| Local UI state | React component | Component state | Open/close drawers, active tab, filters, modals, draft text |
| Persistent browser state | `localStorage` / session storage | Browser | Theme, UI preferences, persisted filters |
| Shell runtime state | `RootLayout` | `__root.tsx` | Nav mode, unread chat count, mobile sheet state |
| MAX bridge runtime state | MAX WebApp bridge wrapper | MAX client runtime | `initData`, `BackButton`, contact capture, closing confirmation, `openMaxLink()` |

## Admin Shell Bootstrap

```mermaid
sequenceDiagram
  participant Browser
  participant Root as RootLayout
  participant Profile as useProfile
  participant Router as TanStack Router
  participant Page as Route page

  Browser->>Root: Load /app/*
  Root->>Profile: fetch current principal
  Profile-->>Root: principal + recruiter/admin profile
  Root->>Root: resolve theme, motion, mobile mode
  Root->>Router: render nav + outlet
  Router->>Page: mount route component
  Page->>Page: fetch page-specific server state with React Query
```

## Candidate Detail Flow

```mermaid
sequenceDiagram
  participant User
  participant Page as CandidateDetailPage
  participant DetailQ as useCandidateDetail
  participant ChannelQ as useCandidateChannelHealth
  participant Actions as useCandidateActions
  participant Query as queryClient

  User->>Page: Open /app/candidates/$candidateId
  Page->>DetailQ: load detail payload
  Page->>ChannelQ: load Telegram channel health summary
  User->>Actions: execute supported mutation
  Actions-->>Page: success message
  Page->>DetailQ: refetch candidate detail
  Page->>ChannelQ: refetch channel state when delivery status changes
  Page->>Query: invalidate ['candidates'] list
```

### What matters
- Detail screen keeps the canonical view model inside `CandidateDetailPage`.
- Mutations must invalidate both detail and list views when they affect candidate status.
- Channel-health UI reflects current supported runtime only; it must not advertise historical MAX runtime as live behavior.

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
  Page->>HealthQ: poll operator channel health snapshot
  Page->>OutboxQ: poll outbox feed with filters
  Page->>LogsQ: poll notification logs with filters
  User->>Mut: retry or cancel outbox item
  Mut-->>Page: success
  Page->>OutboxQ: refetch list
  Page->>HealthQ: next poll reflects queue/degraded changes
```

### What matters
- Delivery tab combines operator health, outbox feed, and notification logs.
- Operator diagnostics must stay behind authenticated admin surfaces.
- Telegram is the only supported live messaging runtime today.

## Telegram Mini App Flow

```mermaid
sequenceDiagram
  participant TG as Telegram client
  participant SPA as tg-app routes
  participant API as backend.apps.admin_api

  TG->>SPA: Open /tg-app/*
  SPA->>API: send Telegram initData-backed requests
  API-->>SPA: recruiter/mobile payloads
  SPA-->>TG: render recruiter workflow
```

## MAX Mini App Candidate Flow

```mermaid
sequenceDiagram
  participant Candidate as MAX client
  participant SPA as /miniapp SPA
  participant Launch as /api/max/launch
  participant Access as /api/candidate-access/*
  participant Chat as MAX chat

  Candidate->>SPA: Open /miniapp from MAX system button
  SPA->>Launch: POST signed initData + optional start_param
  Launch-->>SPA: bound session for existing candidate or new hidden draft intake
  alt first MAX visit without bound context
    Launch-->>SPA: create hidden draft candidate + access session
    SPA->>Access: GET /test1
    Access-->>SPA: shared Test1 payload
  else manual_review_required
    SPA-->>Candidate: render manual-review next-step card
  end
  SPA->>Access: GET /journey, /test1, booking context
  Access-->>SPA: shared candidate journey/Test1/booking payloads
  alt no slots available after Test1
    SPA->>Access: POST /manual-availability
    Access-->>SPA: waiting-slot success + activated candidate state
  end
  alt user chooses chat handoff
    SPA->>Access: POST /chat-handoff
    Access-->>SPA: server-side handoff acknowledged
    SPA-->>Candidate: open MAX chat through explicit user gesture
  end
```

### What matters
- `/miniapp` is a bounded controlled-pilot surface, not a production MAX rollout.
- Critical candidate state stays server-backed through shared `/api/max/launch` and `/api/candidate-access/*`; MAX bridge APIs only supply client runtime helpers.
- Shared candidate journey, Test1, screening, booking, and chat-handoff semantics remain canonical and must not fork into MAX-only business logic.
- Global MAX entry now follows an intake-first path: a hidden draft candidate is created on first launch, Test1 starts immediately, and phone/contact restore remains a bounded recovery path instead of the primary entry flow.
- The surface stays default-off and fail-closed when MAX is disabled or unconfigured.

## Reserved Future Surfaces
- Future standalone candidate web flow remains a target-state surface. It is intentionally excluded from the mounted SPA route tree and from live OpenAPI today.
- Full MAX runtime/channel rollout beyond the bounded pilot remains a target-state surface. The mounted `/miniapp` flow described above is the guarded pilot-only exception, not a production channel commitment.
- SMS / voice fallback remains a target-state integration concern, not a current frontend flow.
