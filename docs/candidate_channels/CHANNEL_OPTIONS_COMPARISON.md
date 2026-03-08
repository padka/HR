# Channel Options Comparison

## How To Read This Comparison

Сравнение ниже опирается на две вещи:

1. фактическую готовность текущего кода;
2. practical viability каналов для РФ/CIS в 2026 году.

Там, где речь идет о риске блокировок, скорости запуска и операционной пригодности, это **архитектурный вывод**, а не обещание провайдера. Там, где речь идет о platform capabilities, опора идет на публичные материалы платформ.

## Short Recommendation

### Launch order

1. **Первым запускать: Candidate Web Flow**
2. **Вторым каналом: MAX или VK Mini Apps как entry layer поверх того же web/journey core**
3. **Резервный контур: SMS deep-link + email fallback**

### Recommended model

**Web-first + messenger-entry + SMS/email fallback**

Причина:

- web дает лучший UX для массового screening и scheduling;
- мессенджеры хороши как acquisition/notification layer;
- SMS/email нужны как delivery fallback, а не как primary runtime;
- второй бот без web core лишь переносит same problem в другой transport.

## Comparative Table

Оценки: `High / Medium / Low` и комментарий.

| Channel | Availability in RF/CIS | Blocking / restriction risk | Cost of ownership | Candidate UX | Mass hiring scale | Launch speed | Integration complexity | Control over journey | Good for tests/forms | Good for interview booking | Good for async recruiter comms | Best role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Candidate Web Portal** | High | Low to Medium | Medium | High | High | Medium | Medium | Very high | Very high | Very high | Medium | Main runtime |
| **PWA over portal** | High | Low to Medium | Medium | High after first visit | High | Medium | Medium | Very high | Very high | Very high | Medium | Portal enhancement |
| **Telegram bot / WebApp** | Medium in current business context | High | Low to Medium | Medium for quick actions, low for long flows | High | Already exists | Low incremental | Low | Low to Medium | Medium | High while channel is reachable | Entry + notifications |
| **MAX bot / mini-app** | Medium | Medium | Medium | Medium | Potentially high, but immature for this repo | Medium | Medium | Medium | Medium | Medium | Medium | Second messenger candidate |
| **VK Mini Apps** | High in RF ecosystem | Medium | Medium | Medium to High | High | Medium | Medium to High | Medium | High | High | Medium | Embedded alternative entry/runtime |
| **WhatsApp Business** | Medium | Medium to High operationally | Medium to High | High for short messaging | High | Medium | Medium | Low to Medium | Low | Medium | Medium to High | Notification-only side channel |
| **SMS flow** | Very high | Low | Medium to High at scale | Low for long flows, high for OTP/reminders | High | Fast | Low to Medium | Low | Very low | Low | Very low | OTP + fallback |
| **Email** | High | Medium deliverability risk | Low | Medium | High | Fast | Low | Medium | Low | Medium via deep link | Medium | Fallback + follow-up |
| **Web chat widget** | High on owned pages | Low to Medium | Medium | Medium | Medium | Medium | Medium | High on owned traffic | Low | Low to Medium | High if threaded | Pre-screen touchpoint |

## Channel-by-Channel Assessment

### 1. Candidate Web Portal

**Why it fits this codebase first**

- already reusable slot APIs and validation logic exist;
- `candidate_id` and invite-token pattern can be extended into web access tokens;
- current biggest gap is durable candidate-facing runtime, not just missing messenger.

**Strengths**

- maximum control over UX and state;
- best place for multi-step анкета, tests, slot picker, resume, status center;
- cleanest foundation for omnichannel architecture;
- easiest way to show “следующее действие”.

**Weaknesses**

- needs auth, access tokens, progress persistence and new frontend routes;
- requires product work on mobile UX;
- needs explicit notification/deep-link strategy to drive return traffic.

**Verdict**

- must be primary investment.

### 2. PWA

PWA не отдельный канал, а усилитель web portal.

**What it gives**

- installable, app-like UX;
- faster re-entry;
- better stickiness for repeated follow-up.

**What it does not solve**

- initial acquisition by itself;
- phone verification and notifications still need other channels.

**Verdict**

- good Phase 2 enhancement, not Phase 0 substitute for portal.

### 3. Telegram

**Strengths**

- уже реализован;
- хорошо работает как quick-start and notification transport;
- recruiters and current ops already trained.

**Weaknesses**

- current single point of failure;
- poor UX for long screening;
- unstable as sole runtime in current market conditions stated by business.

**Verdict**

- keep as adapter, stop treating as core runtime.

### 4. MAX

**Strengths**

- в коде уже есть adapter/webhook foundation;
- платформа явно ориентирована на чат-ботов и мини-приложения;
- platform docs допускают production webhook pattern и deep links.

**Weaknesses**

- текущая repo integration незрелая;
- нужно отдельное GTM validation по candidate adoption;
- нельзя делать на него единственную ставку.

**Verdict**

- разумный второй messenger adapter после decoupling и web MVP.

### 5. VK Mini Apps

**Strengths**

- ближе всего к web-runtime внутри локальной экосистемы;
- подходит для длинных форм лучше, чем классический bot chat;
- аудитория и distribution внутри VK экосистемы сильнее, чем у нового канала.

**Weaknesses**

- extra platform integration layer;
- часть candidate traffic не захочет проходить flow внутри соцсети;
- recruiter communication still better outside embedded app.

**Verdict**

- сильный кандидат на Phase 4, особенно если acquisition already comes from VK ads/community traffic.

### 6. WhatsApp Business

**Strengths**

- привычный chat UX;
- пригоден для массовых уведомлений и service messages;
- можно использовать для коротких transactional nudges.

**Weaknesses**

- ниже control over flow;
- длинные тесты и slot booking внутри WhatsApp неудобны;
- operational onboarding / policy / provider setup adds friction.

**Verdict**

- рассматривать как notification and recovery channel, не как main journey runtime.

### 7. SMS

**Strengths**

- самый универсальный fallback для OTP и resume links;
- не требует установки отдельного приложения;
- best-effort channel when messenger unreachable.

**Weaknesses**

- дорог для длинного общения;
- плох для анкет и сложного branching;
- ограниченный контент и no persistent rich UI.

**Verdict**

- обязателен как fallback and re-entry mechanism.

### 8. Email

**Strengths**

- дешево;
- удобно для magic link и повторного входа;
- хорош для длинных инструкций и post-booking summaries.

**Weaknesses**

- weaker immediate open rate than messenger/SMS;
- deliverability and spam classification matter;
- часть кандидатов на массовом найме менее email-centric.

**Verdict**

- нужен как secondary fallback, но не основной канал для срочных действий.

### 9. Web chat widget

**Strengths**

- полезен на landing pages/job pages;
- снижает трение для первого вопроса;
- может сразу вести в portal.

**Weaknesses**

- сам по себе не заменяет status center и full onboarding;
- сложно вести long-form test entirely in widget;
- требует owned traffic.

**Verdict**

- хороший дополнительно-входной слой, но не first implementation target.

## Practical Ranking By Use Case

### Best channel for primary screening

1. Web portal
2. VK Mini Apps
3. Messenger only for very short pre-qualifying steps

### Best channel for interview booking

1. Web portal
2. VK Mini Apps / embedded web
3. Telegram/MAX only for confirm/cancel/open-link

### Best channel for reminders

1. Preferred messenger
2. SMS fallback
3. Email fallback

### Best channel for recruiter async communication

1. Unified CRM thread + routed outbound messages
2. Candidate portal message center
3. Messenger transport underneath

### Best channel for resume-from-breakpoint

1. SMS/email/messenger deep link to portal
2. Persistent portal session
3. Messenger-only resume as last resort

## What To Launch First

### First

**Candidate Web Flow MVP**

Why:

- biggest business risk is candidate loss before booking;
- this is exactly where web beats messenger;
- it reuses most existing domain logic while removing transport lock-in.

### Second

**MAX or VK Mini Apps**

Decision rule:

- if business acquisition is closer to owned/local messenger strategy and existing code leverage matters more -> **MAX** first;
- if acquisition is already VK-heavy or likely to move there -> **VK Mini Apps** first.

For this repository specifically, **MAX is cheaper as a second adapter from engineering perspective**, because scaffolding already exists. **VK Mini Apps is stronger as a distribution/runtime option**, but it is a larger net-new integration.

### Reserve

**SMS deep links + email fallback**

This should ship before any second full messenger runtime, because it reduces losses across all channels, not just one.

## Recommended Product Model

### Main UX

- candidate gets a link;
- authenticates with minimum friction;
- sees progress, status and next action;
- completes long-form steps in web;
- receives transactional nudges in messenger/SMS/email;
- can always resume from the same point.

### Recommended channel roles

- **Web**: анкета, тест, slot booking, status center, documents
- **Telegram/MAX/VK**: entry, nudges, reminders, quick replies, reopen web flow
- **SMS**: OTP, fallback, critical reminders
- **Email**: backup resume links, longer instructions, post-booking summary

## Sources

Platform capability references used for this comparison:

- MAX developer platform overview: [dev.max.ru/docs](https://dev.max.ru/docs)
- MAX Bot API overview and webhook guidance: [dev.max.ru/docs-api](https://dev.max.ru/docs-api)
- MAX mini-app/help references: [dev.max.ru/help/miniapps](https://dev.max.ru/help/miniapps)
- VK Mini Apps platform overview by VK: [habr.com/ru/companies/vk/articles/961286](https://habr.com/ru/companies/vk/articles/961286/)
- VK Mini Apps web-to-mini-app migration article: [habr.com/ru/companies/vk/articles/771772](https://habr.com/ru/companies/vk/articles/771772/)
- PWA overview: [web.dev/explore/progressive-web-apps](https://web.dev/explore/progressive-web-apps)
- WhatsApp Business overview: [business.whatsapp.com](https://www.whatsapp.com/business/api)

## Assumptions

- Оценка availability/blocking risk сделана как архитектурный вывод: owned web/SMS/email меньше зависят от одного third-party runtime, чем bot-only journey.
- Для MAX/VK/WhatsApp нужен отдельный go-to-market validation по фактической аудитории вакансий и CPL/CPA, но это не меняет архитектурную рекомендацию делать core web-first.
