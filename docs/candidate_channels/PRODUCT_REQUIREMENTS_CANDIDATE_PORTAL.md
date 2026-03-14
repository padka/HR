# Product Requirements: Candidate Portal

## Product Intent

Candidate Portal должен стать основным candidate-facing runtime для прохождения первичного пути найма без зависимости от Telegram.

Portal не заменяет все каналы. Он решает другую задачу:

- хранит progress;
- показывает status and next action;
- позволяет проходить screening, booking, confirm/cancel/reschedule;
- служит anchor point для всех deep links из мессенджеров, SMS и email.

## Business Goals

1. Снизить drop-off до записи на интервью.
2. Устранить зависимость первичного пути от Telegram.
3. Упростить возврат в прерванный сценарий.
4. Дать кандидату прозрачный статус и понятное следующее действие.
5. Сохранить единый профиль кандидата для рекрутера.

## Primary Users

### Candidate in mass hiring funnel

Typical conditions:

- mobile device first;
- короткие сессии;
- нестабильная связь;
- низкая терпимость к сложной регистрации;
- быстрое переключение между каналами.

### Recruiter

Needs:

- видеть единый progress и канал общения;
- понимать, что отправлено и доставлено;
- быстро переводить кандидата в следующий шаг;
- не терять кандидата между screening и booking.

## UX Principles

1. Mobile-first.
2. No password account creation.
3. 1-3 actions per screen.
4. Autosave after each meaningful step.
5. Always show:
   - current status;
   - progress;
   - next action;
   - resume safety.
6. Every reminder opens to the exact unfinished step.
7. Candidate never has to understand internal recruiter statuses.

## Authentication Requirements

### Supported auth modes

#### P0

- one-time deep link token;
- SMS code to phone;
- invite link from recruiter/CRM;
- magic link to email as secondary method.

#### P1

- returning session on same device;
- optional channel linking for Telegram/MAX/VK.

### Auth UX rules

- auth should happen inline, not as a separate “create account” ceremony;
- if candidate arrives via valid deep link, ask only for missing verification;
- if phone already known, show masked number and request one-tap confirmation/OTP;
- if session expired, route back to exact step after re-auth.

## Core Portal Screens

### 1. Entry / landing screen

Purpose:

- explain what will happen in 1-2 lines;
- show expected duration;
- reassure that progress is saved.

Content:

- vacancy/company context;
- “что дальше” summary;
- CTA `Начать` / `Продолжить`.

### 2. Contact verification

Purpose:

- verify phone or email with minimum friction.

Fields:

- phone input;
- OTP code;
- optional email.

Rules:

- prefer phone for mass hiring;
- email optional unless business requires it.

### 3. Candidate profile / pre-screen form

Fields:

- FIO
- phone
- city
- desired position
- optional experience fields
- optional consent checkbox

Rules:

- prefill known data from source;
- validate inline;
- split long form into short sections.

### 4. Screening / Test1

Requirements:

- render questions in web, not messenger-only;
- support branching;
- support validation;
- autosave per answer;
- support text, single-select, multi-select, numeric, date/time, attachment later if needed.

Candidate-facing UX:

- progress bar;
- estimated time;
- “save and continue later” by default, no extra click.

### 5. Slot selection

Requirements:

- list available slots in candidate timezone;
- filter by date;
- show recruiter name if helpful;
- explain what happens after booking.

Actions:

- choose slot;
- request manual scheduling if no slot fits.

### 6. Booking pending / confirmation

States:

- pending recruiter approval;
- confirmed;
- requires reschedule;
- canceled.

Content:

- date/time;
- timezone;
- next action;
- fallback contact path.

### 7. Status center

Core block:

- current stage;
- next action;
- due date / appointment if any;
- what to prepare;
- action buttons.

Candidate-friendly wording examples:

- “Анкета заполнена”
- “Нужно выбрать время собеседования”
- “Собеседование назначено на ...”
- “Подтвердите участие”
- “Ожидайте сообщения рекрутера”

### 8. Communication / messages

Scope for MVP:

- read candidate-facing updates;
- send structured reply or short message to recruiter;
- see recruiter instructions and latest outreach.

P1:

- full threaded communication.

### 9. Documents

P1 or when required by business:

- upload resume;
- upload requested documents;
- show secure upload status.

## Required Candidate Journeys

### Scenario 1. Entry by web link

Flow:

1. Candidate opens link.
2. System identifies campaign/invite and candidate stub if exists.
3. Candidate verifies phone.
4. Candidate sees welcome + expected duration.
5. Candidate completes questionnaire.
6. Candidate completes test.
7. Candidate selects slot.
8. Candidate gets confirmation and status screen.

Success criteria:

- no Telegram dependency;
- progress survives refresh/device interruption;
- recruiter sees same candidate profile.

### Scenario 2. Entry through messenger, continuation in web

Flow:

1. Candidate enters via Telegram/MAX/VK.
2. Short intro message gives one deep link.
3. Candidate opens portal.
4. Portal continues from current journey session.
5. Recruiter sees single thread and single profile.

Success criteria:

- no duplicate candidate record;
- entry channel preserved in analytics;
- continuation point exact.

### Scenario 3. Interrupted scenario

Flow:

1. Candidate closes browser or leaves step unfinished.
2. State autosaves immediately.
3. Reminder goes out with deep link.
4. Candidate returns to same unfinished step.

Success criteria:

- no data loss;
- no forced restart from step 1;
- next action remains obvious.

### Scenario 4. Telegram unavailable

Flow:

1. Notification attempt via Telegram fails or circuit opens.
2. System sends SMS/email fallback with resume link.
3. Candidate opens portal.
4. Recruiter sees channel switch reason and delivery history.

Success criteria:

- critical candidate actions remain possible;
- switch is observable;
- no manual admin intervention required for ordinary fallback.

### Scenario 5. Post-booking communication

Flow:

1. Candidate sees booked slot in status center.
2. Candidate can confirm, cancel or request reschedule.
3. Reminders go out with deep links.
4. Recruiter sees candidate response state and timing.

Success criteria:

- appointment management self-service;
- recruiter receives reaction state;
- candidate always has a current source of truth.

## Functional Requirements

### Portal state and progress

- store current journey session;
- store per-step progress;
- show percent completion or stage progress;
- persist incomplete answers;
- recover after auth/session expiry.

### Next action engine

Portal must always render one primary CTA based on state:

- `Продолжить анкету`
- `Пройти тест`
- `Выбрать время`
- `Подтвердить участие`
- `Загрузить документ`
- `Написать рекрутеру`

### Candidate-facing statuses

Portal should map internal status complexity into a short external taxonomy:

1. `Начало`
2. `Проверяем анкету`
3. `Нужно выбрать время`
4. `Собеседование назначено`
5. `Ожидаем подтверждение`
6. `Ожидайте дальнейших инструкций`
7. `Нужны дополнительные данные`
8. `Процесс завершен`

Internal `CandidateStatus` may remain richer in CRM.

### Notifications

Types:

- auth OTP / magic link
- abandoned-flow reminder
- slot pending
- slot confirmed
- confirm/cancel/reschedule request
- day-before / hours-before reminder
- recruiter message available

Rules:

- every notification contains exact deep link;
- every critical notification has fallback chain;
- quiet hours respected where possible.

## Data Requirements

### Candidate data

- candidate id
- full name
- phone
- email optional
- city
- preferred channel
- linked messenger accounts
- progress state

### Screening data

- answers per question
- validation status
- score/result
- completion timestamps

### Scheduling data

- slot choice
- timezone
- booking state
- cancel/reschedule reason

### Communication data

- last recruiter update
- unread messages
- delivery status summary

## Non-Functional Requirements

### Reliability

- autosave on every meaningful step;
- resume after refresh and session expiration;
- no hard dependency on messenger availability.

### Performance

- mobile 3G/4G friendly;
- initial load lightweight;
- no blocking full-page reloads for step completion.

### Accessibility

- readable on 360px width;
- clear contrast;
- large tap targets;
- plain-language error messages.

### Security

- signed one-time links;
- OTP rate limiting;
- short-lived session tokens;
- audit log for recruiter-visible actions.

## What Moves To Web vs What Stays In Messaging

### Move to web immediately

- анкета;
- screening/test;
- slot picker;
- status center;
- confirm/cancel/reschedule;
- document upload.

### Leave in messaging as lightweight layer

- entry prompt;
- reminders;
- “у вас новое действие”;
- short confirm/cancel actions that open portal if more context is needed.

## MVP Scope

### In MVP

- link-based entry;
- phone verification;
- questionnaire + Test1;
- slot selection;
- booking confirmation;
- status page;
- abandoned-flow resume;
- SMS/email fallback links.

### Out of MVP

- full real-time omnichannel chat;
- document-heavy onboarding;
- advanced self-service profile editing;
- fully customizable journey builder UI.

## Success Metrics

### Product metrics

- start-to-Test1 completion rate;
- Test1 completion-to-slot booking rate;
- booking-to-confirmation rate;
- resumed-session completion rate;
- share of candidates completed without Telegram dependency.

### Operational metrics

- reminder delivery success by channel;
- fallback-triggered save rate;
- recruiter response SLA;
- duplicate candidate rate across channels.

## Open Decisions

1. OTP-only vs OTP + magic link hybrid
2. need for document upload in MVP
3. whether portal thread is read-only or two-way in MVP
4. whether slot approval remains recruiter-mediated in first web release

## Final Product Recommendation

Основной UX должен быть:

**candidate opens link -> verifies number -> continues saved journey -> sees status and next action at every step**

Это даст системе то, чего сейчас нет:

- возобновляемость;
- понятность для кандидата;
- каналонезависимость;
- управляемый drop-off between screening and booking.
