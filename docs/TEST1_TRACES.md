# TEST 1 — Sequence Traces

## 1. Happy path (Test 1 → слот → согласование → подтверждение)
```mermaid
sequenceDiagram
    participant C as Candidate
    participant B as Bot
    participant D as Domain (DB)
    participant R as Recruiter
    participant S as Scheduler

    C->>B: completes Test 1 (callback `t1opt:*`)
    B->>B: `finalize_test1` → share form, show `choose_recruiter`
    C->>B: `pick_rec:<id>`
    B->>D: `get_free_slots_by_recruiter`
    C->>B: `pick_slot:<rec_id>:<slot_id>`
    B->>D: `reserve_slot` (Slot FREE → PENDING)
    B->>R: send slot request (`kb_approve`)
    C->>B: waits (`slot_sent`)
    R->>B: `approve:<slot_id>`
    B->>D: `approve_slot` (PENDING → BOOKED)
    B->>D: `add_notification_log(type="candidate_interview_confirmed")`
    B->>C: send `approved_msg`
    B->>S: `schedule_for_slot` (reminder_24h + confirm_6h + confirm_2h)
    C->>B: `att_yes:<slot_id>`
    B->>D: `confirm_slot_by_candidate` (BOOKED → CONFIRMED)
    B->>C: send link (`att_confirmed_link`)
    B->>S: reschedule reminders (только напоминания без подтверждения)
```

## 2. Нет свободных слотов
```mermaid
sequenceDiagram
    participant C as Candidate
    participant B as Bot
    participant D as Domain
    participant R as Recruiter (optional)

    C->>B: `pick_rec:<id>`
    B->>D: `get_free_slots_by_recruiter` → []
    B->>C: клавиатура без слотов + кнопка «Обновить»
    C->>B: `refresh_slots:<id>`
    B->>D: повторный запрос → []
    B->>C: повторяет `no_slots`
    B->>C: `manual_schedule_prompt` (message + optional tg://user?id)
```

## 3. Перенос по решению рекрутёра
```mermaid
sequenceDiagram
    participant R as Recruiter
    participant B as Bot
    participant D as Domain
    participant C as Candidate
    participant S as Scheduler

    R->>B: `reschedule:<slot_id>`
    B->>D: `get_slot`
    B->>D: `reject_slot` (PENDING/BOOKED/CONFIRMED → FREE)
    B->>S: `cancel_for_slot`
    B->>C: `notify_reschedule` (template `slot_reschedule`, state reset)
    B->>R: ack message «Перенос»
    C->>B: выбирает нового рекрутёра/слот (возврат к flow RecruiterPick)
    (далее повторяется happy-path)
```

## 4. Отказ рекрутёра
```mermaid
sequenceDiagram
    participant R as Recruiter
    participant B as Bot
    participant D as Domain
    participant C as Candidate

    R->>B: `reject:<slot_id>`
    B->>D: `get_slot`
    B->>D: `reject_slot` (→ FREE)
    B->>C: `notify_rejection` (`result_fail`, state flow="rejected")
    B->>R: ack «Отказано»
    C->>B: при необходимости возвращается к `kb_recruiters` (если сценарий продолжается)
```

> См. P0: NotificationLog не очищается в шагах `reject_slot`, что ломает повторный happy-path.
