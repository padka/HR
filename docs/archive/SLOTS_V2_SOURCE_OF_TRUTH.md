# Slots v2: Source of Truth

Дата создания: 2025-11-26
Статус: Living Document (обновляется по мере реализации)

## Цель документа

Зафиксировать единственный источник истины для:
- Статусов слотов и кандидатов
- Таймзон и времени
- API контрактов
- Бизнес-логики и валидаций

---

## 1. Статусы Слотов (SlotStatus)

**Модель:** `backend/domain/models.py` → `SlotStatus`

```python
class SlotStatus:
    FREE = "free"                           # Свободен, можно бронировать
    PENDING = "pending"                     # Зарезервирован системой, ждет подтверждения
    BOOKED = "booked"                       # Забронирован кандидатом
    CONFIRMED_BY_CANDIDATE = "confirmed_by_candidate"  # Подтвержден кандидатом
    CANCELLED = "cancelled"                 # Отменен (может быть?)
```

**Переходы:**
```
FREE → PENDING (candidate reserves)
FREE → BOOKED (admin assigns manually)
PENDING → BOOKED (candidate confirms booking)
PENDING → FREE (timeout/cancel)
BOOKED → CONFIRMED_BY_CANDIDATE (candidate confirms attendance)
BOOKED → FREE (admin cancels / candidate declines)
CONFIRMED_BY_CANDIDATE → FREE (reschedule/cancel)
```

**SQL Source:**
```sql
SELECT status, COUNT(*)
FROM slots
GROUP BY status;
```

**UI Mapping:**
- `FREE` → 🟢 Зеленый badge "Свободен"
- `PENDING` → ⏳ Желтый badge "Ожидает"
- `BOOKED` → 📅 Синий badge "Забронирован"
- `CONFIRMED_BY_CANDIDATE` → ✅ Зеленый badge "Подтвержден"

---

## 2. Статусы Кандидатов (CandidateStatus)

**Модель:** `backend/domain/candidates/status.py` → `CandidateStatus`

**Полный список:**
```python
class CandidateStatus(str, Enum):
    # Testing phase
    TEST1_COMPLETED = "test1_completed"
    WAITING_SLOT = "waiting_slot"
    STALLED_WAITING_SLOT = "stalled_waiting_slot"  # >24h waiting

    # Interview phase
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_CONFIRMED = "interview_confirmed"
    INTERVIEW_DECLINED = "interview_declined"

    # Test 2 phase
    TEST2_SENT = "test2_sent"
    TEST2_COMPLETED = "test2_completed"
    TEST2_FAILED = "test2_failed"

    # Intro day phase
    INTRO_DAY_SCHEDULED = "intro_day_scheduled"
    INTRO_DAY_CONFIRMED_PRELIMINARY = "intro_day_confirmed_preliminary"
    INTRO_DAY_DECLINED_INVITATION = "intro_day_declined_invitation"
    INTRO_DAY_CONFIRMED_DAY_OF = "intro_day_confirmed_day_of"
    INTRO_DAY_DECLINED_DAY_OF = "intro_day_declined_day_of"

    # Final
    HIRED = "hired"
    NOT_HIRED = "not_hired"
```

**Валидные переходы:** см. `STATUS_TRANSITIONS` в `backend/domain/candidates/status.py`

**Ключевые переходы для слотов:**
- `WAITING_SLOT` → `INTERVIEW_SCHEDULED` (when slot assigned)
- `INTERVIEW_SCHEDULED` → `INTERVIEW_CONFIRMED` (when candidate confirms)
- `INTERVIEW_CONFIRMED` → `TEST2_SENT` (after interview)
- `INTERVIEW_CONFIRMED` → `INTRO_DAY_SCHEDULED` (skip Test2, direct to intro)

---

## 3. Таймзоны и Время

### Принципы

1. **Хранение:** Всегда UTC aware datetime в PostgreSQL
2. **API:** Принимаем ISO8601 с timezone или (datetime + timezone_name)
3. **UI:** Отображаем в 3 форматах:
   - UTC (для дебага)
   - Recruiter TZ (основной)
   - Candidate TZ (если есть кандидат)

### Модель Slot

```python
class Slot(Base):
    start_utc: datetime  # MUST be timezone-aware (UTC)
    tz_name: str         # e.g. "Europe/Moscow" - recruiter's timezone
    candidate_tz: str    # e.g. "Asia/Novosibirsk" - candidate's timezone
    duration_min: int    # default 60
```

### Утилиты нормализации

**Локация:** `backend/core/timezone_utils.py` (создать)

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def normalize_to_utc(dt: datetime, tz_name: str = None) -> datetime:
    """Convert any datetime to UTC aware."""
    if dt.tzinfo is None:
        # Naive datetime - assume it's in specified timezone
        if tz_name:
            local_tz = ZoneInfo(tz_name)
            dt = dt.replace(tzinfo=local_tz)
        else:
            # Default to UTC if no timezone specified
            dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)

def to_local_time(dt: datetime, tz_name: str) -> datetime:
    """Convert UTC datetime to local timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    local_tz = ZoneInfo(tz_name)
    return dt.astimezone(local_tz)

def format_for_ui(dt: datetime, tz_name: str, format_str: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime for UI in specified timezone."""
    local_dt = to_local_time(dt, tz_name)
    return local_dt.strftime(format_str)
```

### Правила валидации

- ❌ **НИКОГДА** не сравнивать naive и aware datetime
- ✅ Все сравнения только после нормализации к UTC
- ✅ Все входные данные нормализовать через `normalize_to_utc()`
- ✅ Хранить `tz_name` отдельно для отображения

---

## 4. API Контракты

### GET /api/slots

**Цель:** Получить список слотов с фильтрацией и пагинацией

**Query Parameters:**
```typescript
{
  // Pagination
  page?: number;           // default 1
  per_page?: number;       // default 50, max 200

  // Filters
  status?: SlotStatus[];   // multi-select: ['free', 'booked']
  recruiter_id?: number[];
  city_id?: number[];

  // Date range (ISO8601 UTC)
  start_from?: string;     // "2025-11-26T00:00:00Z"
  start_to?: string;       // "2025-12-03T23:59:59Z"

  // Search
  query?: string;          // search by candidate name, tg_id

  // Sort
  sort_by?: string;        // "start_utc" | "status" | "recruiter"
  sort_dir?: "asc" | "desc";

  // View format
  timezone?: string;       // for time calculations, default "UTC"
}
```

**Response:**
```typescript
{
  items: Array<{
    id: number;
    recruiter_id: number;
    recruiter_name: string;
    city_id: number | null;
    city_name: string | null;
    start_utc: string;       // ISO8601
    start_local: string;     // in recruiter TZ
    start_candidate: string | null;  // in candidate TZ if exists
    duration_min: number;
    status: SlotStatus;
    candidate_tg_id: number | null;
    candidate_fio: string | null;
    candidate_status: CandidateStatus | null;
    tz_name: string;
    candidate_tz: string | null;
    purpose: string;         // "interview" | "intro_day"
  }>;

  pagination: {
    page: number;
    per_page: number;
    total: number;
    pages: number;
  };

  summary: {
    total: number;
    free: number;
    pending: number;
    booked: number;
    confirmed: number;
  };
}
```

### POST /api/slots/bulk_create

**Цель:** Создать серию слотов

**Request Body:**
```typescript
{
  mode: "single" | "series";

  // Single mode
  recruiter_id: number;
  city_id?: number;
  start_datetime: string;  // ISO8601 or local + timezone
  timezone: string;        // "Europe/Moscow"
  duration_min?: number;   // default 60
  purpose?: string;        // default "interview"

  // Series mode
  series?: {
    start_date: string;    // "2025-11-26"
    end_date: string;      // "2025-12-10"
    weekdays: number[];    // [1,2,3,4,5] Monday-Friday
    time_slots: Array<{    // Multiple times per day
      start_time: string;  // "09:00"
      end_time: string;    // "18:00"
      interval_min: number; // 30 or 60
    }>;
  };

  preview_only?: boolean;  // true = don't save, just return preview
}
```

**Response:**
```typescript
{
  created: number;
  slots: Array<SlotPreview>;
  conflicts: Array<{
    slot_index: number;
    reason: string;
    existing_slot_id?: number;
  }>;
}
```

### POST /api/slots/bulk_action

**Request:**
```typescript
{
  slot_ids: number[];
  action: "delete" | "cancel" | "free" | "move" | "reassign";

  // For move
  offset_minutes?: number;  // +30, -15, etc

  // For reassign
  new_recruiter_id?: number;
  new_city_id?: number;

  force?: boolean;  // skip confirmations
}
```

### GET /api/slots/{id}/details

**Response:**
```typescript
{
  slot: SlotDetailed;
  candidate: CandidateInfo | null;
  history: Array<{
    timestamp: string;
    event: string;
    description: string;
    user?: string;
  }>;
  notifications: Array<NotificationInfo>;
  conflicts: Array<ConflictInfo>;
}
```

---

## 5. Известные Проблемы (Fixed)

### ✅ Исправлено в предыдущих коммитах:

1. **NameError: OutboxNotification**
   - Файл: `backend/apps/admin_ui/routers/candidates.py:50`
   - Фикс: Добавлен импорт `from backend.domain.models import OutboxNotification`

2. **IntegrityError: UNIQUE constraint notification_logs**
   - Файл: `backend/domain/repositories.py:846-942`
   - Фикс: Обернута функция `confirm_slot_by_candidate` в try/except IntegrityError

3. **Invalid status transition: INTERVIEW_CONFIRMED -> INTRO_DAY_SCHEDULED**
   - Файл: `backend/domain/candidates/status.py:158-162`
   - Фикс: Добавлен переход в STATUS_TRANSITIONS

### 🔧 Требуют внимания:

1. **Naive/Aware datetime comparisons**
   - Локации: `schedule_manual_candidate_slot`, любые сравнения datetime
   - План: Создать `timezone_utils.py` и нормализовать все входы/выходы

2. **Inconsistent time display**
   - UI показывает разные форматы
   - План: Единый компонент для отображения времени с переключателем UTC/Local

---

## 6. Бизнес-Логика

### Конфликты слотов

**Определение конфликта:**
Два слота конфликтуют если:
1. У одного рекрутера
2. Пересекаются по времени (start1 < end2 AND start2 < end1)
3. Оба не в статусе CANCELLED

**SQL проверка:**
```sql
SELECT s1.id, s2.id
FROM slots s1, slots s2
WHERE s1.recruiter_id = s2.recruiter_id
  AND s1.id < s2.id
  AND s1.start_utc < s2.start_utc + (s2.duration_min || ' minutes')::INTERVAL
  AND s2.start_utc < s1.start_utc + (s1.duration_min || ' minutes')::INTERVAL
  AND s1.status != 'cancelled'
  AND s2.status != 'cancelled';
```

### Правила отмены

- FREE слот: можно удалить сразу
- PENDING/BOOKED: требуется подтверждение
- CONFIRMED_BY_CANDIDATE: требуется force=true + уведомление кандидату

### Автоматические переходы

- PENDING → FREE через 15 минут если не подтвержден
- WAITING_SLOT → STALLED_WAITING_SLOT через 24 часа

---

## 7. Метрики и Мониторинг

### Key Performance Indicators

- **Response Time:** GET /api/slots < 500ms (p95)
- **Conflict Detection:** < 100ms для проверки 1000 слотов
- **Bulk Create:** < 2s для создания 100 слотов

### Логирование

Обязательно логировать:
- Создание/удаление слотов
- Изменение статуса
- Конфликты
- Ошибки TZ

---

## 8. Миграции и Совместимость

### Текущая схема БД

```sql
CREATE TABLE slots (
    id SERIAL PRIMARY KEY,
    recruiter_id INTEGER REFERENCES recruiters(id),
    city_id INTEGER REFERENCES cities(id),
    start_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_min INTEGER DEFAULT 60,
    status VARCHAR(50),
    candidate_tg_id BIGINT,
    candidate_fio VARCHAR(255),
    candidate_tz VARCHAR(100),
    tz_name VARCHAR(100),
    purpose VARCHAR(50) DEFAULT 'interview'
);
```

### Индексы

```sql
CREATE INDEX idx_slots_start_utc ON slots(start_utc);
CREATE INDEX idx_slots_status ON slots(status);
CREATE INDEX idx_slots_recruiter_id ON slots(recruiter_id);
CREATE INDEX idx_slots_candidate_tg_id ON slots(candidate_tg_id);
```

---

## Changelog

- **2025-11-26:** Initial version, documented existing state
- **TBD:** After Phase 1 completion, update with API contracts
- **TBD:** After Phase 2 completion, update with UI states

---

## Ссылки

- Модели: `backend/domain/models.py`
- Кандидаты: `backend/domain/candidates/`
- UI: `backend/apps/admin_ui/templates/slots_list.html`
- Роутер: `backend/apps/admin_ui/routers/slots.py`
