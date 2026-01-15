# Slots v2 - Phase 1 Progress

**Цель:** Фиксы логов + единая TZ-нормализация + API фильтров/пагинации

**Дата начала:** 2025-11-26
**Статус:** В процессе 🟡

---

## Checklist

### ✅ 1. Фиксы логов (Completed)

- [x] **NameError: OutboxNotification**
  - Файл: `backend/apps/admin_ui/routers/candidates.py:50`
  - Решение: Добавлен импорт
  - Коммит: Предыдущая сессия

- [x] **IntegrityError: UNIQUE notification_logs**
  - Файл: `backend/domain/repositories.py:846-942`
  - Решение: Try/except IntegrityError + idempotent handling
  - Коммит: Предыдущая сессия

- [x] **Invalid status transition**
  - Файл: `backend/domain/candidates/status.py:158-162`
  - Решение: Добавлен INTERVIEW_CONFIRMED -> INTRO_DAY_SCHEDULED
  - Коммит: Предыдущая сессия

### ✅ 2. Documentation (Completed)

- [x] **Source of Truth документ**
  - Файл: `docs/SLOTS_V2_SOURCE_OF_TRUTH.md`
  - Содержит: Статусы, таймзоны, API контракты, бизнес-логику
  - Статус: Living document, будет обновляться

### ✅ 3. Timezone Utilities (Completed)

- [x] **Создан модуль timezone_utils**
  - Файл: `backend/core/timezone_utils.py`
  - Функции:
    - `normalize_to_utc()` - конвертация любого datetime в UTC aware
    - `to_local_time()` - конвертация UTC в локальную TZ
    - `format_for_ui()` - форматирование для UI
    - `ensure_aware()` - гарантия timezone-aware
    - `parse_timezone()` - парсинг названий TZ
    - `is_same_moment()` - сравнение моментов времени
    - `datetime_range_overlap()` - проверка пересечения диапазонов

- [x] **Тесты для timezone_utils**
  - Файл: `tests/test_timezone_utils.py`
  - Покрытие: все основные функции + edge cases
  - Запуск: `.venv/bin/python -m pytest tests/test_timezone_utils.py -v`

### ✅ 4. Исправление naive/aware проблем (Completed)

**Выполнено:**
1. ✅ Рефакторинг `backend/core/time_utils.py` - делегирует в timezone_utils
2. ✅ Исправлено 4 места в `backend/apps/bot/services.py` - datetime.now(timezone.utc)
3. ✅ Проверен `backend/domain/repositories.py` - 19 корректных вызовов _to_aware_utc
4. ✅ Проверен `backend/apps/admin_ui/routers/slots.py` - фильтры по датам отсутствуют

**Измененные файлы:**
- [x] `backend/core/time_utils.py` - рефакторинг на timezone_utils
- [x] `backend/apps/bot/services.py:3861` - Test 1 report date
- [x] `backend/apps/bot/services.py:4036` - Test 2 start time
- [x] `backend/apps/bot/services.py:4069` - Test 2 answer timestamp
- [x] `backend/apps/bot/services.py:4188` - Test 2 report date

**Документация:**
- [x] `docs/DATETIME_FIXES_SUMMARY.md` - детальный summary всех исправлений

### 🔲 5. API Endpoints (Pending)

- [ ] **GET /api/slots**
  - Фильтрация: status, recruiter_id, city_id, date range, query
  - Пагинация: page, per_page
  - Сортировка: sort_by, sort_dir
  - Формат ответа: JSON с items + pagination + summary

- [ ] **GET /api/slots/{id}/details**
  - Полная информация о слоте
  - История изменений
  - Уведомления
  - Конфликты

- [ ] **POST /api/slots/bulk_create**
  - Создание серии слотов
  - Preview mode
  - Conflict detection

- [ ] **POST /api/slots/bulk_action**
  - Массовые операции: delete, cancel, move, reassign
  - Force mode

### 🔲 6. Tests (Pending)

- [ ] Unit tests для API endpoints
- [ ] Integration tests для bulk operations
- [ ] E2E test: create → confirm → reschedule
- [ ] Performance test: 1000 slots < 500ms

---

## Следующие шаги

### Немедленно (сегодня)

1. ✅ Создать timezone_utils.py
2. ✅ Написать тесты для timezone_utils
3. ✅ Найти и исправить naive/aware проблемы
4. 🔲 Создать API router для /api/slots

### Завтра

1. Реализовать GET /api/slots с фильтрацией
2. Реализовать GET /api/slots/{id}/details
3. Написать тесты для API
4. Обновить UI для использования нового API

### Потом (Phase 2)

1. Bulk operations API
2. Conflict detection engine
3. Quick Create UI
4. Side panel UI

---

## Критические моменты

### Timezone правила

**ВСЕГДА:**
- ✅ Хранить в БД UTC aware datetime
- ✅ Нормализовать через `normalize_to_utc()` перед сохранением
- ✅ Использовать `to_local_time()` для отображения
- ✅ Передавать timezone_name отдельно от datetime

**НИКОГДА:**
- ❌ Не сравнивать naive и aware datetime
- ❌ Не предполагать timezone по умолчанию без явного указания
- ❌ Не использовать datetime.now() без timezone.utc

### API принципы

**Request:**
```python
# Option 1: ISO8601 with timezone
{
    "start_datetime": "2025-11-26T15:00:00+03:00"
}

# Option 2: Datetime + timezone separately
{
    "start_datetime": "2025-11-26T15:00:00",
    "timezone": "Europe/Moscow"
}
```

**Response:**
```python
{
    "start_utc": "2025-11-26T12:00:00Z",  # Always UTC
    "start_local": "2025-11-26T15:00:00",  # In recruiter TZ
    "timezone": "Europe/Moscow"
}
```

---

## Команды для проверки

```bash
# Запуск тестов timezone utils
.venv/bin/python -m pytest tests/test_timezone_utils.py -v

# Найти все naive datetime сравнения
grep -r "datetime.now()" backend/ --include="*.py" | grep -v "timezone.utc"

# Найти все datetime сравнения
grep -r "< datetime\|> datetime\|== datetime" backend/ --include="*.py"

# Проверить импорты timezone_utils
grep -r "from backend.core.timezone_utils import" backend/ --include="*.py"
```

---

## Метрики

**Цели Phase 1:**
- ✅ 0 naive/aware TypeErrors в логах
- ❌ GET /api/slots response time < 500ms
- ✅ 100% покрытие тестами timezone_utils
- ❌ API docs для всех новых endpoints

**Текущий прогресс:**
- ✅ timezone_utils создан и протестирован (100%)
- ✅ Source of Truth задокументирован (100%)
- ✅ Naive/aware фиксы завершены (100%)
- ❌ API endpoints не созданы (0%)

---

## Риски и блокеры

### Риски

1. **Performance:** Pagination на больших таблицах может быть медленной
   - Митигация: Добавить индексы на start_utc, status, recruiter_id

2. **Backward compatibility:** Изменение timezone logic может сломать старый код
   - Митигация: Поэтапное внедрение, тесты на регрессию

3. **Complexity:** Bulk operations с конфликтами могут быть сложными
   - Митигация: Начать с простых операций, добавлять постепенно

### Блокеры

- Нет блокеров на данный момент

---

## Changelog

- **2025-11-26 15:00:** Phase 1 started
- **2025-11-26 16:00:** Created timezone_utils + tests
- **2025-11-26 17:00:** Documented source of truth
- **2025-11-26 17:15:** Refactored time_utils to use timezone_utils
- **2025-11-26 17:30:** Fixed 4 datetime.now() calls in services.py
- **2025-11-26 17:45:** Verified repositories.py and routers/slots.py
- **2025-11-26 18:00:** Created DATETIME_FIXES_SUMMARY.md - все datetime фиксы завершены ✅
