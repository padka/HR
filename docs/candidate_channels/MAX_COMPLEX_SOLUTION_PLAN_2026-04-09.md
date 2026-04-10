# MAX Complex Solution Plan for RecruitSmart

Дата: `2026-04-09`

Research basis:
- existing local context: [MAX_BOT_READINESS_AUDIT_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_BOT_READINESS_AUDIT_2026-04-09.md), [MAX_IMPLEMENTATION_SPEC_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_IMPLEMENTATION_SPEC_2026-04-09.md)
- primary source of truth: official MAX docs and API docs on [dev.max.ru](https://dev.max.ru/docs)
- secondary signals: official MAX GitHub repository and a small set of public engineering writeups, clearly marked by confidence

Important scope note:
- this document is not a re-audit of RecruitSmart codebase
- this document does not replace the MAX implementation spec
- this document answers a wider product/platform question: how RecruitSmart should use MAX as an ecosystem, not only as a chatbot transport

## 1. Executive Summary

MAX is already more than a bot surface. The official platform currently gives RecruitSmart three materially different surfaces:
- chat bots for acquisition, conversational nudges, service notifications, lightweight branching, and re-entry
- mini apps for richer stateful UX inside MAX without forcing the candidate into an external browser
- channels for one-to-many distribution, onboarding content, employer brand, and internal or semi-internal updates

For RecruitSmart, the strongest near-term format is not `bot only`. The recommended target model is:
- `bot + mini app` as the main candidate path
- `channels` as a supporting layer, not as the transaction surface for candidate workflow

Why:
- the bot is the best entry, reminder, and re-engagement surface
- the mini app is the best place for long forms, slot selection, reschedule, dashboard, instructions, and onboarding artifacts
- channels are useful for distribution and retention, but they are weak as the system of record for candidate actions

The highest-value MAX capabilities for RecruitSmart right now are:
- source-aware deep links for acquisition and attribution
- `requestContact` to reduce friction on phone/contact capture
- mini app launch from bot for screening, scheduling, and candidate dashboard
- validated `WebAppData` / init context for secure server-side identity binding
- bot-side service notifications and restart/re-entry prompts
- official MAX UI and bridge components to keep candidate UX native

Overall recommendation:
- Phase 1 should ship as `bot + mini app`
- Phase 2 should expand into candidate dashboard, onboarding surfaces, and selective channel usage
- Phase 3 can add strategic enhancements such as coordinator flows, richer onboarding automation, and optional advanced device/client capabilities where justified

## 2. Official MAX Capability Map

### 2.1 Bot API

What the official docs confirm:
- MAX supports both webhook and long polling for bot updates, but they cannot be used simultaneously.
- Official help states long polling is for development and testing, while production should use webhook.
- Incoming updates can remain buffered on the MAX side for up to 8 hours.
- Webhooks require a public HTTPS endpoint; official help also states a static IP requirement for webhook production setup.
- If webhook delivery fails, MAX retries notifications. The API method page states up to 10 retries and eventual removal of the subscription if the bot stays unavailable for about a week.
- To stop retry storms after an internal application error, the bot should still return HTTP `200` and handle the failure internally.

Officially visible update/event types:
- `bot_started`
- `message_created`
- `message_callback`
- `message_edited`
- `message_removed`
- `bot_added` / `bot_added_to_chat`
- `bot_removed` / `bot_removed_from_chat`
- `user_added` / `user_added_to_chat`
- `user_removed` / `user_removed_from_chat`
- `chat_title_changed`
- `message_chat_created`

Officially visible bot interaction capabilities:
- send message
- edit message
- delete message
- answer callback
- get current bot identity
- get users
- work with chats and group chats
- upload and send files
- format text with Markdown or HTML

Officially documented keyboard and button types:
- callback button
- link button
- open mini app button
- message button
- request contact button
- request geolocation button

Officially documented limits that matter for product design:
- message text length: up to `4000` characters
- inline keyboard: up to `210` buttons total, `30` rows, `7` buttons per row
- rows containing `link`, `open_app`, `request_geo_location`, or `request_contact` are limited to `3` buttons per row
- link button URL length: up to `2048` characters
- deep-link payload for bot launch: up to `128` characters
- deep-link payload for mini app launch: up to `512` characters
- deep-link support explicitly confirmed in official FAQ for iOS `2.7.0+` and Android `2.9.0+`
- webhook response timeout: `30` seconds
- API guidance recommends staying within `30 rps` to `platform-api.max.ru`
- official FAQ says webhook setup should use HTTPS and static IP

Additional API constraints worth noting:
- official docs state sent messages can be edited only within `24` hours
- official docs state sent messages can be deleted only within `24` hours if the bot has permission
- official docs now require the bot token in the `Authorization` header rather than query params

Officially documented production caveats:
- bots are public in practice: official help says users can find a bot by link or by nickname in search, and “private bot” mode is not currently available
- bot settings changes may trigger re-moderation
- official help says one verified organization can create up to `5` bots
- bot ownership transfer is currently not supported

RecruitSmart implication:
- use the bot as an acquisition and orchestration shell, not as the only UI surface
- keep all heavy candidate actions off callback-only UX where possible
- do not architect around “hidden bot” assumptions; if a confidential candidate flow is needed, protect it through invite/token logic, not bot discoverability

Key official sources:
- [MAX docs overview](https://dev.max.ru/docs)
- [Chatbot setup and deep links](https://dev.max.ru/docs/chatbots/bots-coding/prepare)
- [JavaScript bot library docs](https://dev.max.ru/docs/chatbots/bots-coding/library/js)
- [API methods index](https://dev.max.ru/docs-api)
- [Webhook subscription method](https://dev.max.ru/docs-api/methods/POST/subscriptions)
- [Events FAQ](https://dev.max.ru/help/events)
- [Chatbots FAQ](https://dev.max.ru/help/chatbots)
- [Deep links FAQ](https://dev.max.ru/help/deeplinks)

### 2.2 Mini Apps

What the official docs confirm:
- MAX mini apps are standard web applications embedded inside MAX
- they are launched from a bot or by direct MAX app link
- mini apps cannot meaningfully operate in isolation from MAX platform context if they need identity, chat context, or bridge APIs
- MAX recommends adapting UX to official [MAX UI](https://dev.max.ru/ui/components/Avatar.Overlay) for native consistency
- mini apps are the right surface when chat UI is too constrained for the task

Officially documented launch options:
- button of type `open_app`
- button of type `link`
- direct app link like `https://max.ru/app/<app-name>`
- mini app deep-link payload via `startapp`

Important official product constraints:
- only one mini app can be open at a time in the client
- mini app URLs must be HTTPS
- launch context is delivered through `WebAppData`, platform, version, and start parameters
- official docs reviewed do not expose a full server-side lifecycle model beyond launch context, bridge events, and closure handling

Where mini apps are stronger than pure bot chat for RecruitSmart:
- profile form and long questionnaire
- scheduling UI with many slots, dates, filters, and confirmation states
- candidate dashboard with current stage, appointment details, address, checklist, and support actions
- reschedule and cancellation UX that would be clumsy in callback-only chat
- post-scheduling onboarding content and documents

Key official sources:
- [Mini apps overview](https://dev.max.ru/docs/webapps)
- [Mini app validation](https://dev.max.ru/docs/webapps/validation)
- [MAX Bridge](https://dev.max.ru/docs/webapps/bridge)

### 2.3 MAX Bridge and Client Capabilities

The official bridge inventory shows a broader capability set than RecruitSmart needs for v1. The relevant subset:

Launch and context:
- `getLaunchParams`
- `initData` / `WebAppData`
- platform and version context
- `startapp` payload or related launch params for context-aware open

High-value interaction capabilities:
- `requestContact`
- `BackButton`
- `ClosingBehavior`
- `Popup`
- `Linking`
- `Share`
- `Clipboard`
- `Viewport`
- `MainButton`
- `SecondaryButton`

Potentially useful later:
- `CloudStorage`
- `DeviceStorage`
- `SecureStorage`
- `Geolocation` / `LocationManager`
- `ScanQrPopup`
- `requestDocument`
- `BiometryManager`
- `requestWriteAccess`
- `requestHomeScreen`

Practical reading for RecruitSmart:
- `requestContact` is the single highest-value bridge feature for reducing friction on phone capture
- `BackButton`, closing confirmation, and popups matter for form completion and accidental exit control
- `Linking` and MAX links are useful for moving candidates between bot, mini app, office maps, and instructions
- `Share` is useful for referral or bringing in a friend, but not core to candidate processing
- official deep-link FAQ also documents `https://max.ru/:share?text=<...>` as a native share entry point, which is more relevant for referral or post-booking self-share than for the core candidate flow
- `DeviceStorage` and `SecureStorage` are not strong phase-1 primitives for business identity or scheduling state because RecruitSmart must remain cross-device and server-authoritative
- `Geolocation` is useful only if office navigation or branch routing materially improves conversion
- `BiometryManager` is a low-priority capability in HR flow unless there is a very specific compliance or local device-unlock scenario
- `ScanQrPopup` is promising for office-day check-in or candidate self-arrival, but not a phase-1 blocker

Client-support caveat:
- the reviewed bridge page clearly exposes capability names, but the exact support matrix for mobile vs desktop vs web was not fully explicit in the reviewed lines
- treat advanced client APIs as “officially present, client support to be validated in hands-on smoke tests before rollout”

Key official source:
- [MAX Bridge](https://dev.max.ru/docs/webapps/bridge)

### 2.4 Validation and Security

The official mini app security model in the reviewed docs is HMAC-based, not trust-on-client.

What the official docs confirm:
- mini app launch data is passed through `WebAppData`
- the payload includes fields like `auth_date`, `chat`, `user`, `query_id`, and `hash`
- validation is based on HMAC-SHA256
- the secret key is derived as `HMAC_SHA256("WebAppData", Bot Token)`
- the signed payload is reconstructed from sorted key-value pairs and compared with the original `hash`
- official docs expect server-side validation
- `auth_date` freshness should be checked to reduce replay risk

Security implications for RecruitSmart:
- candidate identity in mini app should be accepted only after server validation of `WebAppData`
- the backend must enforce freshness windows and reject stale launch payloads
- bot token handling becomes security-critical because it is part of verification
- mini app launch context should not be used as the only business authorization mechanism for irreversible actions
- signed action tokens for scheduling/confirm/reschedule should remain server-authoritative even inside mini app

Important correction:
- earlier ecosystem summaries sometimes confuse MAX validation with Telegram-style variants or alternate signature models
- the reviewed official MAX validation page specifically describes HMAC-SHA256 over `WebAppData`

Key official source:
- [Mini app validation](https://dev.max.ru/docs/webapps/validation)

### 2.5 Channels

What the official docs confirm:
- MAX supports public and private channels
- public channels are searchable and linkable
- private channels are invite-based only
- private channels can require join approval
- private channels can be created without partner-platform onboarding, directly by a MAX user with a Russian phone number
- public business channels have stronger organizational and moderation mechanics
- official docs currently allow one public business channel with chosen title and generated nickname, plus additional channels that mirror A+ verified resources on other platforms
- private channels are effectively unlimited

RecruitSmart fit:
- public channel is useful for employer brand, recruiting campaigns, job fair announcements, and onboarding-news style communication
- private channels are useful for onboarding cohorts, branch-specific instructions, or internal coordinator updates
- channels are weak for transactional candidate actions because they do not replace secure per-candidate state, authorization, or idempotent backend actions

Key official sources:
- [Channels overview in docs](https://dev.max.ru/docs)
- [Channels help/FAQ](https://dev.max.ru/help/channels)
- [Channel creation docs](https://dev.max.ru/docs/channels/create)

### 2.6 Platform, Moderation, and Operational Constraints

What the official docs and help pages confirm:
- partner platform access is available to Russian-resident legal entities and sole proprietors
- reviewed partner-connection help also states that self-employed users, individuals, and non-residents cannot currently pass platform verification
- partner-platform operations are web-only today
- bots and mini apps go through moderation before broad availability
- support response may take up to 5 business days according to the official support page
- organization verification is a prerequisite for commercial partner usage
- content and functionality must follow platform rules and Russian legal requirements

Operational implications for RecruitSmart:
- rollout planning must include legal/account readiness, not just engineering readiness
- moderation and re-moderation can affect release windows
- do not assume instant bot/app edits in production if a moderation step is triggered
- keep core candidate funnel resilient to a channel outage by retaining browser/portal fallback

Key official sources:
- [Platform overview](https://dev.max.ru/docs)
- [Partner connection](https://dev.max.ru/docs/maxbusiness/connection)
- [Bot API terms](https://dev.max.ru/docs/legal/terms/maxbot_api/)
- [Mini app terms](https://dev.max.ru/docs/legal/terms/miniapps)
- [Support page](https://dev.max.ru/help/support)

### 2.7 Table 1. MAX Capability Inventory

| Capability | Source | Official / unofficial | Current maturity / confidence | Relevance to RecruitSmart | Notes |
| --- | --- | --- | --- | --- | --- |
| Bot updates and webhooks | [POST /subscriptions](https://dev.max.ru/docs-api/methods/POST/subscriptions), [Events FAQ](https://dev.max.ru/help/events) | Official | High | High | Core for bot runtime and reminders |
| Long polling | [Events FAQ](https://dev.max.ru/help/events) | Official | High | Medium | Dev/test only, not recommended for prod |
| Deep links for bots | [Bot prepare docs](https://dev.max.ru/docs/chatbots/bots-coding/prepare), [Deep links FAQ](https://dev.max.ru/help/deeplinks) | Official | High | High | Strong acquisition and attribution surface |
| Deep links for mini apps | [Bot prepare docs](https://dev.max.ru/docs/chatbots/bots-coding/prepare) | Official | High | High | Useful for source-aware screening/scheduling entry |
| Inline keyboard and buttons | [JS bot docs](https://dev.max.ru/docs/chatbots/bots-coding/library/js) | Official | High | High | Good for lightweight branching only |
| Message formatting and edits | [JS bot docs](https://dev.max.ru/docs/chatbots/bots-coding/library/js), [API docs](https://dev.max.ru/docs-api) | Official | High | Medium | Needed for confirmations and service messages |
| File attachments | [JS bot docs](https://dev.max.ru/docs/chatbots/bots-coding/library/js) | Official | High | Medium | Good for instructions and onboarding files |
| Mini apps | [Mini apps overview](https://dev.max.ru/docs/webapps) | Official | High | High | Best stateful UX surface in MAX |
| MAX Bridge | [Bridge docs](https://dev.max.ru/docs/webapps/bridge) | Official | Medium-High | High | Exact per-client support needs validation |
| `requestContact` | [Bridge docs](https://dev.max.ru/docs/webapps/bridge), [JS bot docs](https://dev.max.ru/docs/chatbots/bots-coding/library/js) | Official | High | High | High conversion value for contact capture |
| `BackButton` and closing confirmation | [Bridge docs](https://dev.max.ru/docs/webapps/bridge) | Official | Medium-High | High | Important for form completion and accidental close protection |
| DeviceStorage / SecureStorage | [Bridge docs](https://dev.max.ru/docs/webapps/bridge) | Official | Medium | Medium | Useful later, not safe as source of truth |
| QR / document / biometry APIs | [Bridge docs](https://dev.max.ru/docs/webapps/bridge) | Official | Medium | Low-Medium | Later-stage enhancements only |
| WebAppData validation | [Validation docs](https://dev.max.ru/docs/webapps/validation) | Official | High | High | Required for secure mini app identity |
| Public channels | [Platform docs](https://dev.max.ru/docs), [Channels help](https://dev.max.ru/help/channels) | Official | High | Medium | Good for employer brand and onboarding content |
| Private channels | [Channels help](https://dev.max.ru/help/channels) | Official | High | Medium | Useful for cohorts, branches, internal comms |
| MAX UI component library | [MAX UI](https://dev.max.ru/ui/components/Avatar.Overlay) | Official | Medium-High | High | Helps mini app feel native and lower UX friction |
| Official TypeScript bot SDK repo | [GitHub repo](https://github.com/max-messenger/max-bot-api-client-ts) | Official | High | Medium | Good for examples and conventions |
| Habr engineering articles | [Example article](https://habr.com/en/articles/1016164/) | Unofficial | Medium-Low | Low-Medium | Useful for developer experience signals, not source of truth |

## 3. External Research Summary

### 3.1 Sources reviewed beyond the formal docs

Official ecosystem signals:
- [max-messenger/max-bot-api-client-ts](https://github.com/max-messenger/max-bot-api-client-ts)

Public engineering/community materials:
- [Habr: MAX Bot API + CRM integration walkthrough](https://habr.com/en/articles/1016164/)

### 3.2 What these sources add

Official GitHub repository adds:
- practical examples of event handler registration
- error-handling expectations in library usage
- evidence that MAX is serious enough to provide maintained SDK tooling and examples

Public engineering articles add:
- hands-on confirmation that developers are already wiring MAX into CRM-like flows
- practical notes on bot creation and basic event handling
- qualitative signal that the platform is young enough for docs and real-world patterns to still be converging

### 3.3 Reliability assessment

- official MAX GitHub repositories: high reliability for implementation idioms, medium reliability for policy/limits
- Habr or community articles: useful as experience reports only
- if community material conflicts with official docs, trust official docs

### 3.4 Key external takeaways for RecruitSmart

- MAX is mature enough for a serious candidate-facing pilot, but not mature enough to justify overcommitting to rarely used advanced APIs in phase 1
- the best early leverage comes from combining stable official primitives: bot updates, deep links, open-app flows, validated mini app context, and native UI controls

## 4. RecruitSmart Use-Case Mapping

### 4.1 Capability-to-use-case table

| Capability | Description | Use case in RecruitSmart | Value | Complexity | Recommended phase |
| --- | --- | --- | --- | --- | --- |
| Bot deep links | Source-aware entry into bot or app | Vacancy, city, recruiter source, ad attribution | High | Low | Phase 1 |
| `bot_started` and `message_created` | Candidate entry and lightweight conversational flow | Welcome, quick pre-qualification, re-entry prompts | High | Low | Phase 1 |
| Callback buttons | Short branching in chat | Quick yes/no, continue, open scheduling, confirm intent | Medium | Low | Phase 1 |
| `requestContact` in bot or mini app | Native contact-share request | Phone capture without manual typing | High | Low-Medium | Phase 1 |
| Mini app launch from bot | Rich in-chat application surface | Move from short bot flow into screening and scheduling | High | Medium | Phase 1 |
| Validated `WebAppData` | Trusted launch context for server | Secure bind/rebind of candidate session | High | Medium | Phase 1 |
| Candidate dashboard mini app | Persistent status surface | Current stage, interview card, address, checklist | High | Medium | Phase 1 |
| Mini app scheduling UI | Calendar-like stateful actions | Pick slot, confirm, reschedule, cancel | High | Medium | Phase 1 |
| Bot reminders | Asynchronous nudges | Resume questionnaire, interview reminder, incomplete booking reminder | High | Low | Phase 1 |
| MAX UI | Native design system for mini app | Lower friction and higher trust in candidate UX | Medium-High | Medium | Phase 1 |
| Channels public | Broadcast surface | Employer brand, hiring campaigns, office news | Medium | Low-Medium | Phase 2 |
| Channels private | Controlled cohort communication | Onboarding groups, office-specific updates | Medium | Low-Medium | Phase 2 |
| DeviceStorage / SecureStorage | Local client persistence | Remember local draft hints, UI state, last tab | Medium | Medium | Phase 2 |
| Share capability | Native sharing | Referral links, invite a friend, candidate sends map/instructions to self | Medium | Medium | Phase 2 |
| Geolocation / maps links | Location support | Office route help, nearest branch suggestion | Medium | Medium | Phase 2 |
| QR scanner | Camera-based scan | Office arrival check-in, document handoff token scan | Low-Medium | Medium | Phase 3 |
| Request document upload | Native document request | Post-offer onboarding or document collection | Medium | Medium-High | Phase 3 |
| Biometry | Device-level secure auth | Special trust-sensitive action confirmation | Low | High | Phase 3 or avoid |

### 4.2 Candidate acquisition / entry

Recommended usage:
- use bot deep links by vacancy, city, source, and campaign
- encode attribution in `start` or `startapp` payload within official length limits
- keep payload small and signed; resolve full metadata server-side
- if the candidate comes from a recruiter-issued invite, bot should land on a personalized path
- if the candidate comes from public advertising, bot should collect contact and route into generic intake

Why MAX is useful here:
- deep links are native to the platform
- the bot can immediately give context, trust signals, and next-step CTA
- source-aware payloads allow clean analytics without forcing the candidate to an external landing page first

### 4.3 Candidate qualification

Bot-only mode is good when:
- the step is short
- answers are binary or small-choice
- the candidate needs almost no scrolling or review

Mini app mode is better when:
- there are many fields
- answers need validation and draft persistence
- the candidate needs to see progress, previous answers, or supporting help text

Hybrid mode is the best default for RecruitSmart:
- bot handles greeting, first intent, and low-friction early questions
- mini app handles the “real form” and stateful workflow
- bot remains the reminder and recovery layer

### 4.4 Contact collection

Recommended product design:
- ask for contact very early
- prefer `requestContact` over manual phone entry
- still support manual fallback for users who deny or cannot share contact
- store explicit provenance of contact capture: bot share, mini app share, or manual input

Why it matters:
- contact collection is one of the highest-friction points in candidate flow
- native contact sharing directly improves completion probability and identity linkage quality

### 4.5 Interview scheduling

Recommended split:
- bot shows candidate that scheduling is available and gives a single clear CTA
- mini app performs slot browsing, reservation confirmation, reschedule, and cancel
- bot confirms outcome and sends service notifications

Why:
- slot UX becomes much clearer in mini app
- chat callbacks are weak for complex date/time selection, conflict recovery, and state explanation
- a single canonical scheduling backend can still power both surfaces

### 4.6 Candidate dashboard / status

Recommended use:
- a mini app should become the “candidate cabinet” in MAX
- it should show stage, next required action, interview card, address, instructions, and recruiter/system notices
- bot messages should deep-link back into the exact relevant mini app section

This gives RecruitSmart something stronger than “a bot with questions”:
- persistent self-service surface
- lower support load
- better re-entry after interruption

### 4.7 Onboarding / post-scheduling

Recommended use:
- bot for reminders and deadline nudges
- mini app for checklist, office instructions, FAQ, documents, and orientation materials
- channels only if the content is cohort-wide or company-wide and does not require per-candidate authorization

### 4.8 Internal or semi-internal scenarios

Potential fit:
- private channel per office, region, or onboarding cohort
- internal coordinator channel for office announcements or training updates
- not recommended as the primary recruiter workflow surface for v1

## 5. Recommended Product Architecture for MAX

Recommended target model:
- `bot + mini app + channels`

But with clear role separation:

Core path:
- MAX bot
- MAX mini app
- RecruitSmart backend as system of record

Supporting layer:
- MAX channels

### 5.1 Roles of each layer

MAX bot:
- acquisition entry point
- source-aware deep-link landing
- lightweight qualification
- reminders and recovery
- service notifications
- trust-building conversational shell

MAX mini app:
- profile and screening completion
- scheduling and rescheduling
- candidate dashboard
- onboarding checklist and instructions
- persistent self-service surface inside MAX

Channels:
- employer-brand broadcasting
- office or cohort announcements
- onboarding news or FAQ distribution
- internal/semi-internal distribution where one-to-many messaging is enough

RecruitSmart backend:
- identity binding
- canonical candidate workflow
- scheduling source of truth
- notification rules
- analytics and attribution

### 5.2 Core path and supporting path

Core path:
1. Candidate enters through bot deep link.
2. Bot performs quick orientation and contact capture.
3. Bot opens mini app for full screening and scheduling.
4. Backend validates context and persists all state.
5. Bot handles nudges, reminders, and re-entry.
6. Mini app becomes candidate cabinet for ongoing interaction.

Supporting path:
- channels deliver one-to-many information before or after transactional steps

### 5.3 Why not bot-only

Bot-only would leave product value on the table:
- weaker scheduling UX
- weaker dashboard/re-entry UX
- higher candidate friction on long forms
- more complex callback state handling

### 5.4 Why not channels as a primary layer

Channels do not solve:
- candidate identity binding
- secure per-candidate actions
- scheduling state
- reschedule and cancel workflows

## 6. Candidate Journey in MAX: Recommended Design

### 6.1 Recommended end-to-end journey

1. Start
- candidate enters by vacancy/city/source deep link
- bot recognizes source and presents the correct intro

2. Contact capture
- bot asks for contact through `requestContact`
- if denied, bot offers manual fallback

3. Quick qualification in bot
- bot asks a short set of high-signal questions only
- goal is to avoid wasting time on obviously mismatched candidates

4. Move into mini app
- bot opens mini app for full profile, screening, and statusful steps
- mini app validates launch context server-side before unlocking candidate actions

5. Screening and profile
- candidate completes form with validation, draft save, and progress feedback

6. Scheduling
- candidate sees available slots in mini app
- candidate confirms booking, requests reschedule, or cancels where allowed

7. Confirmation
- bot sends concise confirmation
- mini app shows the current interview card, address, time, and preparation instructions

8. Reminder and re-entry
- if candidate abandons flow, bot nudges with a CTA back into the relevant mini app state
- candidate can resume unfinished scheduling or profile completion

9. Preparation to visit
- mini app shows checklist, location details, FAQ, and contact/help actions
- optional private/public channel invitation only if it adds clear value

10. Post-interview
- bot handles status update notifications where appropriate
- mini app remains the surface for next steps, documents, or onboarding content

### 6.2 Table 3. Bot vs Mini App vs Channel Fit

| Scenario | Best surface | Why | Risks |
| --- | --- | --- | --- |
| Vacancy/source entry | Bot | Fast, native, attribution-friendly | Public bot discoverability requires secure backend checks |
| Quick qualification | Bot | Low friction for simple prompts | Longer forms quickly degrade UX |
| Contact share | Bot or mini app | Native `requestContact` reduces friction | Must support manual fallback |
| Full profile form | Mini app | Better validation, layout, progress, review | Requires strong server-side validation |
| Slot selection | Mini app | Better for many options and conflicts | Need disciplined state recovery |
| Reschedule/cancel | Mini app | Better for explanations and confirmation states | Must guard against duplicate writes |
| Service confirmation | Bot | Best async surface | Message overload if overused |
| Candidate dashboard | Mini app | Persistent self-service surface | Needs strong deep-link re-entry design |
| Onboarding checklist | Mini app | Rich content, better structure | Can become cluttered if overloaded |
| Employer brand/news | Public channel | Broadcast-native | Not a secure transactional surface |
| Cohort updates / office instructions | Private channel | Good one-to-many controlled communication | Membership moderation overhead |
| Internal coordinator announcements | Private channel | Simple internal dissemination | Not a replacement for operational systems |

## 7. Phase Plan

### 7.1 Phase 1: must-have

Goal:
- deliver a strong MAX candidate solution without overexpanding platform surface area

Include:
- bot deep links with source attribution
- bot welcome and lightweight qualification
- `requestContact` with manual fallback
- mini app for profile/screening
- mini app for scheduling/reschedule/cancel
- validated `WebAppData` on server
- candidate dashboard with current status and next action
- bot reminders and confirmations
- official MAX UI adoption for core mini app screens

Do not include:
- advanced device APIs as business-critical logic
- channel-heavy dependency in candidate core path
- biometry or QR as required steps

### 7.2 Phase 2: high-value expansion

Include:
- richer dashboard with office instructions, maps, checklist, FAQ
- private/public channel strategy where content value is proven
- share-driven referral or invite mechanics
- selective use of local storage for UX hints and draft convenience
- better onboarding content after scheduling
- office-specific or role-specific announcement surfaces

### 7.3 Phase 3: strategic enhancements

Include:
- QR-based office check-in or arrival confirmation if operationally justified
- document request flows if HR/legal approves
- advanced internal workflows in MAX for coordinators or recruiters
- careful evaluation of secure storage or biometry only if there is a specific business/security case

### 7.4 Table 2. Phase Recommendation

| Capability | Phase 1 / 2 / 3 | Why now / why later |
| --- | --- | --- |
| Bot deep links | Phase 1 | Highest acquisition and attribution value, low complexity |
| Quick qualification bot flow | Phase 1 | Fast value, low UX cost |
| `requestContact` | Phase 1 | Strong friction reduction in a critical step |
| Mini app screening/profile | Phase 1 | Strongest upgrade over bot-only UX |
| Mini app scheduling | Phase 1 | Highest-value transactional improvement |
| Candidate dashboard | Phase 1 | Essential for re-entry and self-service |
| Bot reminders | Phase 1 | Natural use of chat surface |
| MAX UI alignment | Phase 1 | Improves trust and usability immediately |
| Public/private channels | Phase 2 | Useful, but not required for core candidate transaction path |
| Share capability | Phase 2 | Valuable after core flow is stable |
| DeviceStorage / SecureStorage | Phase 2 | Better as UX enhancement than as core dependency |
| Maps/geolocation help | Phase 2 | High utility only after interview workflow is stable |
| QR / document capture | Phase 3 | Requires operational proof and policy clarity |
| Biometry | Phase 3 | High complexity, low immediate recruiting value |

## 8. Capability Prioritization Matrix

| Capability | Phase | Business value | Implementation complexity | UX impact | Dependency / blockers | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| Deep links with attribution | 1 | High | Low | High | Signed payload discipline | Do now |
| Bot contact capture | 1 | High | Low-Medium | High | Contact fallback path | Do now |
| Mini app screening | 1 | High | Medium | High | Server validation | Do now |
| Mini app scheduling | 1 | High | Medium | High | Shared scheduling contracts | Do now |
| Candidate dashboard | 1 | High | Medium | High | Re-entry routing | Do now |
| MAX UI adoption | 1 | Medium | Medium | Medium-High | Design bandwidth | Do now |
| Public channel | 2 | Medium | Low-Medium | Medium | Content ownership | Add after core flow |
| Private cohort channels | 2 | Medium | Low-Medium | Medium | Moderator ownership | Add selectively |
| Local storage enhancements | 2 | Medium | Medium | Medium | Client support checks | Add selectively |
| Referral/share flows | 2 | Medium | Medium | Medium | Analytics model | Add after attribution stabilizes |
| QR check-in | 3 | Low-Medium | Medium | Medium | Operational process change | Later only |
| Document intake in MAX | 3 | Medium | Medium-High | Medium | Legal/policy review | Later only |
| Biometric unlock | 3 | Low | High | Low-Medium | Client support and HR policy | Avoid unless strong need |

## 9. Risks and Constraints

### 9.1 Product risks

- forcing too much of the funnel into chat will hurt completion for long forms and scheduling
- overloading the mini app with every future feature will create a cluttered candidate cabinet
- using channels as a transactional surface will create confusion and poor accountability

### 9.2 Technical risks

- assuming advanced bridge APIs work uniformly across all MAX clients without smoke validation
- using local storage or client context as a source of truth instead of the backend
- underestimating webhook retry semantics and duplicate delivery behavior
- not constraining deep-link payload design to official limits

### 9.3 Platform risks

- moderation or partner-verification delays can block rollout timing
- official docs still look early-stage in places; exact capabilities may evolve
- some operational requirements are stated in FAQ/help rather than in API method pages

### 9.4 Moderation, legal, and operational risks

- commercial use depends on organizational eligibility and verification
- mini apps and bots must comply with platform rules and Russian legal requirements
- public bot discoverability means private workflows must be protected through business auth, not obscurity

### 9.5 Rollout risks

- shipping bot-only first can create a UX trap and rework later
- shipping too many surfaces in one wave can increase operational complexity before the funnel is stable
- channels without clear ownership can become stale and damage trust

### 9.6 Known documentation gaps or inconsistencies

- webhook security details are mostly consistent, but the exact wording around certificate support and infrastructure requirements appears split between API pages and FAQ/help surfaces
- reviewed official material exposes a real inconsistency: the API overview snippet says webhooks support HTTPS including self-signed certificates, while FAQ/help guidance frames production webhook setup around secure HTTPS and static IP. Production recommendation should follow the stricter interpretation: public CA-issued certs only, no reliance on self-signed behavior
- exact support matrix for advanced bridge APIs on mobile/desktop/web was not fully confirmed from the reviewed official lines
- exact callback payload size limit was not explicitly confirmed in the reviewed official pages

Recommended stance:
- treat strictest official interpretation as production baseline
- validate advanced bridge capabilities with real client smoke tests before committing product design to them

## 10. Detailed Recommendations for Next Implementation Wave

What to do immediately after the current MAX channel implementation stabilizes:
- add source-aware deep-link taxonomy for vacancy, city, and campaign attribution
- move all heavy profile and scheduling UX into mini app screens
- keep bot focused on entry, contact capture, reminders, and concise service messaging
- implement a first-class candidate dashboard inside the mini app
- validate `WebAppData` on server for every privileged mini app session start

What to design into architecture early:
- explicit routing between bot CTAs and exact mini app sections
- signed compact start payloads resolved server-side
- channel-agnostic backend contracts so MAX mini app does not invent its own business rules
- feature flags for:
  - mini app screening enablement
  - mini app scheduling enablement
  - requestContact usage
  - public/private channel invitations

What to postpone deliberately:
- channels as part of the required candidate funnel
- secure storage as an authorization primitive
- QR and biometric capabilities
- document-heavy onboarding inside MAX unless HR/legal requirements are aligned

What not to do:
- do not make the mini app a thin shell over chat-only decisions
- do not let channel strategy drive core funnel design
- do not build around unofficial or weakly confirmed MAX behaviors

## 11. Final Recommendation

RecruitSmart should not stop at “MAX bot parity”. The platform already supports a materially stronger model.

Recommended product shape:
- bot as acquisition and orchestration shell
- mini app as the primary transactional and self-service surface
- channels as optional amplification and onboarding surfaces

Most important MAX capabilities to adopt:
- source-aware deep links
- requestContact
- validated mini app launch context
- mini app scheduling and dashboard
- bot reminders and re-entry

Capabilities that should stay out of the first wave:
- channels as a required step
- advanced device APIs as core business dependencies
- biometry and QR unless there is a proven operational use case

The best way to get platform value without unnecessary complexity:
- keep Phase 1 narrow but strong
- let bot and mini app each do what they are best at
- add channels only where they clearly improve reach, onboarding, or retention without becoming a hidden second workflow

## RECOMMENDED MAX STRATEGY FOR RECRUITSMART

1. What is the ideal solution format for RecruitSmart in MAX?

`Bot + mini app` as the core solution, with `channels` as a supporting layer.

2. What must remain in the bot?

- acquisition entry
- source-aware start logic
- lightweight qualification
- contact capture prompt
- reminders
- service notifications
- re-entry nudges back into the right mini app state

3. What is better moved into the mini app?

- long questionnaire and profile completion
- slot browsing and booking
- reschedule and cancel flows
- candidate dashboard and current status
- interview card, office instructions, checklist, FAQ, and onboarding materials

4. Is there value in using channels, and for what?

Yes, but not for the core transaction path.

Use channels for:
- employer brand and recruiting campaigns
- office or cohort announcements
- onboarding information that is shared by many candidates
- internal or semi-internal coordinator communication

5. Which MAX capabilities give the largest UX, conversion, or control lift?

- deep links with attribution
- `requestContact`
- mini app launch from bot
- server-validated `WebAppData`
- candidate dashboard mini app
- bot reminders tied to exact mini app recovery points

6. Which platform constraints influence architecture the most?

- webhook-only expectation for production
- public bot discoverability
- moderation and organization-verification requirements
- deep-link payload limits
- incomplete certainty around advanced bridge support across all client types

7. What 3-wave roadmap is recommended?

Phase 1:
- bot entry, contact capture, mini app screening, mini app scheduling, candidate dashboard, bot reminders

Phase 2:
- richer onboarding surfaces, channels where justified, local UX storage enhancements, maps/share/referral mechanics

Phase 3:
- QR/document/advanced internal workflows, and only selective advanced device capabilities where they have proven business value
