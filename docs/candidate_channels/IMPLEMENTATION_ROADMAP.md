# Implementation Roadmap

## Strategic Direction

Target rollout:

1. снять жесткую зависимость от Telegram;
2. запустить web-first candidate path;
3. добавить delivery fallback;
4. подключить второй messenger adapter к тому же core;
5. улучшить recruiter-candidate communication и analytics.

## Quick Wins Before Major Build

### Quick win 1. Deep-link every critical Telegram message into future portal

Value:

- снижает vendor lock-in;
- не требует сразу переписывать весь bot flow.

### Quick win 2. Normalize candidate addressing to `candidate_id`

Value:

- снижает стоимость всех следующих этапов;
- уменьшает technical debt around `telegram_id`.

### Quick win 3. Add channel/delivery metadata to analytics

Value:

- позволит измерять реальные потери между каналами уже на MVP.

## Stage 0. Discovery / Audit

### Result

- карта текущей логики intake/screening/scheduling/notifications;
- список reuse points and blockers;
- as-is candidate journeys;
- risk register;
- target model recommendation.

### Dependencies

- доступ к живому коду;
- подтверждение бизнес-priorities по каналам и регионам.

### Complexity

- Medium

### Risks

- переоценка готовности Max/VK without GTM validation;
- недооценка объема refactor around Telegram-specific status/reminder APIs.

### Business value

- High

### Production rollout

- docs only; no prod impact.

## Stage 1. Architectural Decoupling

### Goal

Вынести candidate core из Telegram-centric orchestration, не ломая текущий bot flow.

### Main work

- ввести `candidate_id`-first service boundaries;
- добавить channel accounts / access tokens;
- ввести `journey_session` storage;
- адаптировать status projection from journey state;
- переписать reminder/chat/notification orchestration на candidate-centric addressing;
- выделить reusable step handlers for screening and scheduling.

### Result

- Telegram перестает быть source of truth для journey state;
- bot становится adapter over shared services;
- появляется база для portal auth и fallback chains.

### Dependencies

- Stage 0 artifacts;
- согласование новых DB tables and migration plan.

### Complexity

- High

### Risks

- регрессии в текущем bot flow;
- временное coexistence old and new status logic;
- сложность миграции reminder jobs.

### Business value

- Very high

### What can ship progressively

- internal-only migrations;
- new identity tables;
- dual-write analytics;
- bot continues using old UX while new core stores progress.

## Stage 2. Candidate Web Flow MVP

### Goal

Запустить first independent candidate-facing runtime в вебе.

### Main work

- mobile-first portal;
- auth via OTP / magic link / one-time invite;
- profile intake and Test1 web rendering;
- progress autosave and resume;
- slot selection and booking;
- status page with next action;
- post-booking confirmation screen.

### Result

- кандидат может пройти путь от входа до записи без Telegram;
- recruiter sees the same candidate profile in CRM;
- web path becomes primary fallback and likely primary journey.

### Dependencies

- Stage 1 identity/journey APIs;
- message templates for deep links;
- minimal design system reuse in frontend.

### Complexity

- High

### Risks

- auth friction if OTP UX is poor;
- mobile UX regressions if portal is built desktop-first;
- incomplete parity with current bot copy/logic.

### Business value

- Very high

### What can ship progressively

- city-limited beta;
- only for new campaigns first;
- web screening first, booking second if needed;
- opt-in switch from bot to web.

## Stage 3. Notification Fallback

### Goal

Добавить resilient delivery chain around candidate actions.

### Main work

- SMS/email adapters;
- fallback rules per message type;
- delivery telemetry;
- channel switch events in CRM;
- reminder deep links;
- unreachable-candidate escalation to recruiter.

### Result

- критические reminders and resume nudges больше не зависят от одного мессенджера;
- recruiter sees why candidate was switched to fallback.

### Dependencies

- Stage 1 orchestration layer;
- Stage 2 portal deep links;
- provider contracts for SMS/email.

### Complexity

- Medium

### Risks

- cost growth on SMS;
- deliverability/compliance;
- over-notification if fallback thresholds wrong.

### Business value

- High

### What can ship progressively

- OTP via SMS first;
- then resume links;
- then booking reminders;
- then full fallback chains.

## Stage 4. Second Channel Integration

### Goal

Добавить второй non-Telegram entry/notification channel поверх shared journey core.

### Options

- MAX first if engineering leverage and local messenger strategy matter most;
- VK Mini Apps first if acquisition is VK-heavy and embedded app distribution is strategically stronger.

### Main work

- adapter implementation;
- account linking;
- entry handoff to portal;
- channel-specific templates/buttons;
- analytics attribution.

### Result

- омниканальный entry layer;
- Telegram stops being the only conversational gateway.

### Dependencies

- Stage 1-3 complete enough;
- GTM decision on channel priority.

### Complexity

- Medium

### Risks

- platform adoption may lag engineering investment;
- premature second messenger before portal maturity can dilute focus.

### Business value

- Medium to High

### What can ship progressively

- notification-only adapter;
- entry + deep-link adapter;
- only then richer embedded runtime if needed.

## Stage 5. Recruiter-Candidate Communication Improvements

### Goal

Сделать единый thread и action center вместо Telegram-only recruiter messaging.

### Main work

- unified thread in CRM;
- candidate-facing updates in portal;
- outbound routing by preferred channel;
- recruiter SLA indicators;
- next-best-action recommendations;
- reschedule/cancel from portal and routed notifications.

### Result

- handoff between bot/web/recruiter becomes seamless;
- no-channel candidates remain operationally manageable;
- recruiter workload becomes more observable.

### Dependencies

- Stage 1 identity and communication abstractions;
- Stage 2 portal;
- Stage 3 delivery telemetry.

### Complexity

- Medium to High

### Risks

- recruiter process change management;
- ambiguity between portal thread and messenger thread;
- partial omnichannel state until all adapters aligned.

### Business value

- High

### What can ship progressively

- delivery status in CRM;
- portal status center;
- channel-aware outbound send;
- unified thread later in same phase.

## Stage 6. Analytics & Optimization

### Goal

Сделать funnel управляемым по каналам и шагам.

### Main work

- normalized channel attribution;
- drop-off per journey step;
- channel conversion dashboards;
- fallback effectiveness metrics;
- experiment support for copy and step order;
- recruiter response SLA.

### Result

- product and ops teams see where candidates are lost;
- можно управлять конверсией, а не только реагировать на сбои.

### Dependencies

- telemetry from Stages 1-5.

### Complexity

- Medium

### Risks

- noisy data if old and new events coexist too long;
- missing campaign attribution reduces usefulness.

### Business value

- High

### What can ship progressively

- first dashboards on web vs Telegram completion;
- then delivery/fallback dashboards;
- then experiments and optimization loops.

## Recommended Rollout Sequence

### MVP slice

1. Stage 1 partial: identity + journey session foundation
2. Stage 2 partial: web screening + resume + slot booking
3. Stage 3 partial: SMS deep-link fallback

This MVP already removes the most dangerous dependency.

### After MVP

4. recruiter communication improvements
5. second messenger adapter
6. advanced analytics and optimization

## Suggested Timeline Envelope

Это не фиксированный promise, а realistic engineering envelope для команды среднего размера:

- Stage 1: 3-5 weeks
- Stage 2: 4-7 weeks
- Stage 3: 2-3 weeks
- Stage 4: 2-4 weeks
- Stage 5: 3-5 weeks
- Stage 6: 2-4 weeks

Total path to robust multi-channel foundation:

- **lean MVP**: 7-12 weeks
- **operationally mature omnichannel version**: 12-24 weeks

## Priority Matrix

| Stage | Business value | Urgency | Technical leverage | Ship priority |
| --- | --- | --- | --- | --- |
| 1. Architectural decoupling | Very high | Very high | Very high | P0 |
| 2. Candidate Web Flow MVP | Very high | Very high | Very high | P0 |
| 3. Notification fallback | High | High | High | P0 |
| 5. Recruiter communication improvements | High | Medium | High | P1 |
| 4. Second channel integration | Medium to High | Medium | Medium | P1 |
| 6. Analytics & optimization | High | Medium | High | P1 |

## Recommended First Production Cut

### Production cut A

- web link auth;
- screening in web;
- slot booking in web;
- candidate status page;
- SMS fallback for resume/booking reminder.

### Production cut B

- recruiter sees channel history and delivery state;
- Telegram becomes entry + notification adapter;
- portal becomes default continuation path.

### Production cut C

- second messenger adapter;
- omnichannel thread improvements;
- channel conversion dashboards.

## Major Blockers To Manage Early

- candidate auth method decision: OTP vs magic link vs hybrid;
- safe migrations for new identity/session tables;
- keeping current bot flow live during decoupling;
- provider selection for SMS/email;
- event taxonomy and analytics compatibility.

## Final Recommendation

Не стоит начинать с “давайте быстро добавим MAX/VK-бот”. Это снизит risk only partially и зафиксирует тот же каналозависимый долг в новой форме.

Первым в прод должен пойти:

**Stage 1 + Stage 2 + minimal Stage 3**

То есть:

**shared candidate core + web portal MVP + SMS/email fallback**
