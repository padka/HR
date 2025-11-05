# Backlog задач по результатам аудита кодовой базы

**Дата создания:** 2025-11-04
**Источник:** Комплексный аудит кодовой базы recruitsmart_admin

---

## Легенда приоритетов

- **P0 (Critical)** - Блокирует production, требует немедленного исправления
- **P1 (High)** - Критично для бизнеса, исправить в течение недели
- **P2 (Medium)** - Важно, исправить в течение месяца
- **P3 (Low)** - Улучшения, исправить когда возможно

**Оценка сложности:** T-shirt sizes (XS/S/M/L/XL)

---

## Sprint 0: Критические проблемы безопасности (немедленно)

### SEC-001: Ротация утекших credentials [P0]
**Категория:** Security
**Оценка:** S (1-2 часа)
**Файлы:** `.env`

**Описание:**
Обнаружены реальные production credentials в .env файле:
- BOT_TOKEN с реальным Telegram токеном
- ADMIN_PASSWORD: `Nafetomn2001`
- SESSION_SECRET: слабый секрет
- ADMIN_CHAT_ID: `7588303412`

**Acceptance Criteria:**
- [ ] Отозвать текущий Telegram bot token через @BotFather
- [ ] Создать новый bot token
- [ ] Изменить ADMIN_PASSWORD на сильный пароль (16+ символов)
- [ ] Сгенерировать новый SESSION_SECRET (32+ случайных байта)
- [ ] Удалить .env из рабочей директории
- [ ] Проверить git history на наличие .env в коммитах
- [ ] Настроить переменные окружения на сервере
- [ ] Обновить документацию по развертыванию

**Связанные задачи:** SEC-002, SEC-003

---

### SEC-002: Удалить .env из рабочей директории [P0]
**Категория:** Security
**Оценка:** XS (15 минут)

**Описание:**
Файл .env присутствует в рабочей директории и содержит секреты.

**Acceptance Criteria:**
- [ ] Удалить .env из файловой системы
- [ ] Убедиться что .env в .gitignore (уже есть)
- [ ] Использовать только переменные окружения
- [ ] Обновить README с инструкциями по настройке env vars

---

### SEC-003: Генерация сильного SESSION_SECRET [P0]
**Категория:** Security
**Оценка:** XS (30 минут)
**Файлы:** `backend/core/settings.py:151-155`, `.env.example:50`

**Описание:**
SESSION_SECRET использует слабое значение "change-me-session-secret", что позволяет подделывать сессии.

**Acceptance Criteria:**
- [ ] Обновить .env.example с примером сильного секрета
- [ ] Добавить валидацию в settings.py: отклонять слабые секреты типа "change-me"
- [ ] Документировать требования: минимум 32 байта, случайные символы
- [ ] Добавить команду для генерации секрета: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Обновить документацию

**Пример кода:**
```python
# В settings.py добавить валидацию
if session_secret in ["change-me", "change-me-session-secret", "secret"]:
    raise ValueError("SESSION_SECRET must be changed from default value")
if len(session_secret) < 32:
    raise ValueError("SESSION_SECRET must be at least 32 characters")
```

---

## Sprint 1: Критические баги (неделя 1)

### BUG-001: P0 Bug - NotificationLog не очищается при reschedule [P0]
**Категория:** Bug
**Оценка:** M (1-2 дня)
**Файлы:** `backend/domain/repositories.py:966-1019`, `tests/audit_failing_tests/test_notification_logs.py`

**Описание:**
При отклонении/переносе слота NotificationLog не удаляется корректно, что блокирует отправку уведомлений новым кандидатам.

**Root Cause:**
NotificationLog имеет unique constraint на (type, booking_id, candidate_tg_id), но при очистке используется только booking_id.

**Acceptance Criteria:**
- [ ] Обновить функцию `reject_slot()` для корректного удаления NotificationLog
- [ ] Обновить функцию `reschedule_slot()` аналогично
- [ ] Добавить миграцию если нужны изменения схемы
- [ ] Перенести тест из `audit_failing_tests/` в основную suite
- [ ] Тест должен пройти успешно
- [ ] Добавить интеграционный тест для полного flow

**Связанные файлы:**
- `backend/domain/repositories.py:966-1019` (reject_slot)
- `backend/domain/repositories.py` (reschedule_slot)
- `tests/audit_failing_tests/test_notification_logs.py`

---

### BUG-002: P1 Bug - Двойной booking после подтверждения [P1]
**Категория:** Bug
**Оценка:** S (2-4 часа)
**Файлы:** `backend/domain/repositories.py:794-924`, `tests/audit_failing_tests/test_double_booking.py`

**Описание:**
Кандидат с подтвержденным слотом может забронировать второй слот с тем же рекрутером.

**Root Cause:**
В функции `reserve_slot()` проверка существующих бронирований не включает статус `CONFIRMED_BY_CANDIDATE`.

**Acceptance Criteria:**
- [ ] Добавить `SlotStatus.CONFIRMED_BY_CANDIDATE` в проверку (строка 856)
- [ ] Перенести тест из `audit_failing_tests/` в основную suite
- [ ] Тест должен пройти успешно
- [ ] Добавить тест для edge case: подтвержденный + попытка забронировать у другого рекрутера (должно работать)
- [ ] Обновить документацию бизнес-логики

**Код исправления:**
```python
# backend/domain/repositories.py:850-857
func.lower(Slot.status).in_([
    SlotStatus.PENDING,
    SlotStatus.BOOKED,
    SlotStatus.CONFIRMED_BY_CANDIDATE,  # ДОБАВИТЬ ЭТУ СТРОКУ
])
```

---

### SEC-004: Добавить CSRF защиту [P1]
**Категория:** Security
**Оценка:** L (2-3 дня)
**Файлы:** `backend/apps/admin_ui/app.py`, все templates

**Описание:**
Отсутствует CSRF защита на всех state-changing операциях. Возможна атака через вредоносную страницу.

**Уязвимые endpoints:**
- DELETE `/slots/{id}` - удаление слотов
- POST `/slots/delete_all` - удаление всех слотов
- POST `/slots/{id}/outcome` - установка результатов интервью
- POST `/candidates/{id}/toggle` - изменение статуса кандидата
- POST `/api/bot/integration` - переключение бота

**Acceptance Criteria:**
- [ ] Выбрать CSRF библиотеку (starlette-csrf или fastapi-csrf)
- [ ] Добавить CSRF middleware в app.py
- [ ] Добавить CSRF токены во все формы в templates
- [ ] Обновить JavaScript для включения CSRF токена в AJAX запросы
- [ ] Написать тесты для проверки CSRF защиты
- [ ] Убедиться что SameSite=strict сохранен (уже есть)
- [ ] Обновить документацию

**Пример реализации:**
```python
from starlette_csrf import CSRFMiddleware

app.add_middleware(
    CSRFMiddleware,
    secret=settings.session_secret,
    cookie_name="csrf_token",
    header_name="X-CSRF-Token",
)
```

---

### SEC-005: Добавить Rate Limiting [P1]
**Категория:** Security
**Оценка:** M (1-2 дня)
**Файлы:** `backend/apps/admin_ui/app.py`, `backend/apps/admin_ui/security.py`

**Описание:**
Отсутствует rate limiting на:
- Login attempts (возможен brute-force)
- API endpoints (возможен DoS)
- Bot message endpoints

**Acceptance Criteria:**
- [ ] Добавить slowapi или fastapi-limiter
- [ ] Настроить rate limiting для login: 5 попыток / 15 минут / IP
- [ ] Настроить rate limiting для API: 100 запросов / минуту / IP
- [ ] Настроить rate limiting для bot endpoints: 30 запросов / минуту / user
- [ ] Добавить Redis backend для распределенного rate limiting (опционально)
- [ ] Добавить кастомные error messages при превышении лимита
- [ ] Написать тесты
- [ ] Добавить логирование попыток превышения лимита

**Пример:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/auth/login")
@limiter.limit("5/15minutes")
async def login(...):
    ...
```

---

## Sprint 2: Архитектурный рефакторинг (неделя 2-3)

### ARCH-001: Разбить services.py God-class [P1]
**Категория:** Architecture
**Оценка:** XL (5-7 дней)
**Файлы:** `backend/apps/bot/services.py` (4,224 строки!)

**Описание:**
Файл services.py содержит 60+ функций с разными ответственностями, что делает его непригодным для поддержки.

**Plan:**
Разбить на 6 модулей:
1. `notification_service.py` - NotificationService class и retry логика
2. `test1_service.py` - Test 1 flow handlers
3. `test2_service.py` - Test 2 flow handlers
4. `slot_service.py` - Slot booking/approval логика
5. `message_service.py` - Messaging utilities и templates
6. `state_service.py` - State manager helpers

**Acceptance Criteria:**
- [ ] Создать структуру директорий: `backend/apps/bot/services/`
- [ ] Перенести NotificationService в notification_service.py (~1000 строк)
- [ ] Перенести Test 1 логику в test1_service.py (~800 строк)
- [ ] Перенести Test 2 логику в test2_service.py (~700 строк)
- [ ] Перенести slot handlers в slot_service.py (~900 строк)
- [ ] Перенести message helpers в message_service.py (~500 строк)
- [ ] Перенести state helpers в state_service.py (~300 строк)
- [ ] Обновить все импорты в проекте
- [ ] Все тесты должны пройти без изменений
- [ ] Обновить документацию архитектуры

**Риски:**
- Большой масштаб изменений
- Возможны breaking changes
- Требуется тщательное тестирование

**Рекомендация:** Разбить на подзадачи по каждому модулю

---

### ARCH-002: Разбить repositories.py на domain repositories [P2]
**Категория:** Architecture
**Оценка:** L (3-4 дня)
**Файлы:** `backend/domain/repositories.py` (1,028 строк)

**Описание:**
Файл repositories.py содержит 30+ функций для разных domain entities.

**Plan:**
Создать структуру:
```
backend/domain/repositories/
  __init__.py
  recruiter_repository.py
  city_repository.py
  slot_repository.py
  notification_repository.py
  template_repository.py
```

**Acceptance Criteria:**
- [ ] Создать директорию `backend/domain/repositories/`
- [ ] Перенести recruiter queries в recruiter_repository.py
- [ ] Перенести city queries в city_repository.py
- [ ] Перенести slot queries в slot_repository.py (самый большой)
- [ ] Перенести notification queries в notification_repository.py
- [ ] Перенести template queries в template_repository.py
- [ ] Обновить __init__.py с re-exports для обратной совместимости
- [ ] Обновить все импорты
- [ ] Все тесты должны пройти
- [ ] Code coverage не должен упасть

---

### ARCH-003: Разрешить циркулярную зависимость admin_ui ↔ bot [P1]
**Категория:** Architecture
**Оценка:** L (3-5 дней)
**Файлы:** `backend/apps/admin_ui/`, `backend/apps/bot/`

**Описание:**
admin_ui напрямую импортирует из bot, создавая tight coupling.

**Проблемные импорты:**
- `from backend.apps.bot.config import DEFAULT_BOT_PROPERTIES`
- `from backend.apps.bot.reminders import get_reminder_service`
- `from backend.apps.bot.services import NotificationService, get_state_manager`

**Plan:**
1. Создать протоколы в `backend/domain/interfaces/`
2. Вынести общую логику в domain layer
3. Использовать dependency injection

**Acceptance Criteria:**
- [ ] Создать `backend/domain/interfaces/notification_service.py` с Protocol
- [ ] Создать `backend/domain/interfaces/state_manager.py` с Protocol
- [ ] Создать `backend/domain/interfaces/reminder_service.py` с Protocol
- [ ] Перенести DEFAULT_BOT_PROPERTIES в settings.py или domain
- [ ] Обновить admin_ui для использования интерфейсов
- [ ] Убрать все прямые импорты из bot в admin_ui
- [ ] Настроить dependency injection (можно через depends в FastAPI)
- [ ] Все тесты должны пройти
- [ ] Нарисовать новую архитектурную диаграму

**Пример Protocol:**
```python
# backend/domain/interfaces/notification_service.py
from typing import Protocol

class NotificationServiceProtocol(Protocol):
    async def send_confirmation(self, slot_id: int) -> bool: ...
    async def send_reminder(self, slot_id: int) -> bool: ...
```

---

## Sprint 3: Безопасность и качество кода (неделя 4-5)

### SEC-006: Исправить XSS уязвимости в templates [P1]
**Категория:** Security
**Оценка:** M (1-2 дня)
**Файлы:** `backend/apps/admin_ui/templates/*.html`

**Описание:**
JavaScript использует innerHTML с user-controlled данными.

**Уязвимые места:**
- `templates/slots_list.html:694-710` - innerHTML для recruiter данных
- `templates/index.html:573, 598` - innerHTML для dashboard
- `templates/candidates_detail.html` - множество мест

**Acceptance Criteria:**
- [ ] Заменить все `innerHTML` на `textContent` для user data
- [ ] Audit всех templates на предмет XSS
- [ ] Убедиться что Jinja2 autoescape включен
- [ ] Добавить sanitization для всех user inputs в models
- [ ] Написать тесты для XSS vectors
- [ ] Провести manual testing с payloads типа `<img src=x onerror=alert(1)>`
- [ ] Обновить sanitizers.py если нужно

**Пример исправления:**
```javascript
// Было:
slotRecruiter.innerHTML = `<span>${recruiterName}</span>`;

// Стало:
const span = document.createElement('span');
span.textContent = recruiterName;
slotRecruiter.appendChild(span);
```

---

### CODE-001: Исправить exception handling [P2]
**Категория:** Code Quality
**Оценка:** L (3-4 дня)
**Файлы:** Множество файлов по всему проекту

**Описание:**
50+ мест с `except Exception: pass` без логирования.

**Примеры:**
- `repositories.py:920` - silent failure при sync кандидата
- `services.py:3011` - except Exception: pass
- `services.py:2171` - except Exception: city = None

**Acceptance Criteria:**
- [ ] Найти все `except Exception:` в проекте (grep)
- [ ] Для каждого случая:
  - Заменить на конкретное исключение (IntegrityError, ValueError, etc.)
  - Добавить logging с контекстом
  - Определить правильную стратегию обработки
- [ ] Создать custom exceptions для domain errors в `backend/domain/exceptions.py`
- [ ] Обновить documentation с best practices
- [ ] Code review для проверки

**Пример рефакторинга:**
```python
# Было:
try:
    await create_or_update_user(...)
except Exception:
    pass

# Стало:
try:
    await create_or_update_user(...)
except IntegrityError as exc:
    logger.error(
        "Failed to sync candidate",
        exc_info=exc,
        extra={"candidate_id": candidate_tg_id}
    )
    # Allow flow to continue but track failure
except Exception as exc:
    logger.exception("Unexpected error syncing candidate")
    raise
```

---

### CODE-002: Вынести hardcoded значения в configuration [P2]
**Категория:** Code Quality
**Оценка:** S (4-6 часов)
**Файлы:** `backend/apps/bot/config.py`, `backend/apps/bot/services.py`

**Описание:**
Множество hardcoded значений в коде.

**Список:**
- `PASS_THRESHOLD = 0.75` в config.py:24
- `MAX_ATTEMPTS = 3` в config.py
- `TIME_LIMIT = 120` в config.py
- `https://telemost.yandex.ru/j/REPLACE_ME` в services.py:4047
- `https://telemost.yandex.ru/j/SMART_ONBOARDING` в migrations/0002:35

**Acceptance Criteria:**
- [ ] Добавить все значения в `backend/core/settings.py`
- [ ] Добавить в .env.example с документацией
- [ ] Заменить все hardcoded значения на settings
- [ ] Добавить валидацию для critical settings (например PASS_THRESHOLD должен быть 0-1)
- [ ] Обновить миграцию 0002 для использования settings
- [ ] Обновить документацию

**Пример:**
```python
# В settings.py
test_pass_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
test_max_attempts: int = Field(default=3, ge=1, le=10)
test_time_limit_seconds: int = Field(default=120, ge=30)
default_telemost_url: str = "https://telemost.yandex.ru/j/REPLACE_ME"
```

---

### CODE-003: Рефакторинг длинных функций [P2]
**Категория:** Code Quality
**Оценка:** M (2-3 дня)
**Файлы:** `backend/apps/bot/services.py`

**Описание:**
Несколько функций превышают 100 строк с множественной вложенностью.

**Целевые функции:**
- `save_test1_answer` (145 строк: 2674-2819)
- `finalize_test2` (133 строки)
- `finalize_test1` (120+ строк)
- `handle_approve_slot` (130+ строк)

**Acceptance Criteria:**
- [ ] Для каждой функции:
  - Выделить helper methods
  - Максимум 50 строк на функцию
  - Максимум 2-3 уровня вложенности
  - Единая ответственность
- [ ] Написать unit tests для новых helper functions
- [ ] Все существующие тесты должны пройти
- [ ] Улучшить читаемость кода

**Пример рефакторинга:**
```python
# Было: 145 строк в одной функции
async def save_test1_answer(...):
    # Много логики
    # Много if/else
    # Много вложенности

# Стало: разбито на helper functions
async def save_test1_answer(...):
    answer_data = await _parse_answer_data(...)
    validation_result = _validate_answer(answer_data)
    if not validation_result.is_valid:
        return await _handle_invalid_answer(...)

    await _save_to_database(answer_data)
    await _update_candidate_state(...)
    return await _send_next_question(...)
```

---

## Sprint 4: Database & Performance (неделя 6)

### DB-001: Настроить connection pool [P1]
**Категория:** Database
**Оценка:** S (2-3 часа)
**Файлы:** `backend/core/db.py`

**Описание:**
Отсутствует явная настройка connection pool, используются дефолтные значения (pool_size=5).

**Acceptance Criteria:**
- [ ] Добавить настройки в settings.py для connection pool
- [ ] Настроить async_engine с параметрами:
  - pool_size=20
  - max_overflow=10
  - pool_timeout=30
  - pool_pre_ping=True
  - pool_recycle=3600
- [ ] Добавить документацию по настройке
- [ ] Добавить логирование pool statistics
- [ ] Протестировать под нагрузкой

**Код:**
```python
from backend.core.settings import get_settings

settings = get_settings()

async_engine: AsyncEngine = create_async_engine(
    settings.database_url_async,
    echo=settings.sql_echo,
    future=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

---

### DB-002: Добавить недостающие индексы [P2]
**Категория:** Database
**Оценка:** M (1 день)
**Файлы:** `backend/domain/models.py`, создать новую миграцию

**Описание:**
Отсутствуют индексы на часто запрашиваемых полях.

**Требуемые индексы:**
1. `Slot.start_utc` - range queries
2. Composite `(Slot.status, Slot.recruiter_id)` - filtered queries
3. Composite `(OutboxNotification.status, OutboxNotification.next_retry_at)` - worker polling

**Acceptance Criteria:**
- [ ] Создать миграцию 0020_add_performance_indexes.py
- [ ] Добавить индексы:
  ```python
  Index('ix_slots_start_utc', 'start_utc'),
  Index('ix_slots_status_recruiter', 'status', 'recruiter_id'),
  Index('ix_outbox_status_retry', 'status', 'next_retry_at'),
  ```
- [ ] Применить миграцию на test DB
- [ ] Написать тесты для проверки performance improvement
- [ ] Протестировать на SQLite и PostgreSQL
- [ ] Измерить performance до/после (EXPLAIN QUERY PLAN)
- [ ] Обновить документацию

---

### DB-003: Исправить N+1 queries [P2]
**Категория:** Database
**Оценка:** M (1-2 дня)
**Файлы:** `backend/apps/bot/services.py:2158-2195`

**Описание:**
В функции `_build_slot_snapshot` выполняются отдельные запросы для recruiter и city.

**Acceptance Criteria:**
- [ ] Найти все места с потенциальными N+1 queries
- [ ] Добавить eager loading везде где нужно:
  ```python
  .options(
      selectinload(Slot.recruiter),
      selectinload(Slot.city),
      selectinload(Slot.candidate_city)
  )
  ```
- [ ] Написать performance тесты
- [ ] Использовать pytest-benchmark для измерений
- [ ] Убедиться что количество запросов не растет с количеством слотов
- [ ] Обновить documentation с best practices

---

## Sprint 5: Testing & DevOps (неделя 7-8)

### TEST-001: Увеличить test coverage до 90% [P2]
**Категория:** Testing
**Оценка:** XL (5-7 дней)

**Описание:**
Текущий coverage ~85%, есть gaps в критичных areas.

**Plan:**
1. Настроить pytest-cov для отслеживания coverage
2. Найти uncovered code
3. Написать тесты для критичных paths

**Acceptance Criteria:**
- [ ] Настроить pytest-cov в CI/CD
- [ ] Установить минимальный threshold 90%
- [ ] Добавить coverage badge в README
- [ ] Покрыть тестами:
  - Error handling paths (все except блоки)
  - Notification retry logic
  - Template rendering edge cases
  - Slot booking race conditions
  - State machine transitions
- [ ] Все critical paths должны иметь 100% coverage
- [ ] Генерировать HTML coverage report

**Команды:**
```bash
pytest --cov=backend --cov-report=html --cov-report=term --cov-fail-under=90
```

---

### TEST-002: Добавить интеграционные тесты [P2]
**Категория:** Testing
**Оценка:** L (3-4 дня)

**Описание:**
Большинство тестов - unit tests, нет end-to-end integration tests.

**Требуемые тесты:**
1. Полный candidate journey (Test 1 → Booking → Confirmation → Interview)
2. Admin UI → Bot integration
3. Notification delivery flow
4. Slot lifecycle с concurrency

**Acceptance Criteria:**
- [ ] Создать `tests/integration/` директорию
- [ ] Написать `test_candidate_journey.py` - полный E2E flow
- [ ] Написать `test_admin_bot_integration.py`
- [ ] Написать `test_notification_delivery.py`
- [ ] Написать `test_slot_concurrency.py`
- [ ] Тесты должны использовать реальную БД (не моки)
- [ ] Тесты должны быть изолированы и идемпотентны
- [ ] Добавить в CI/CD pipeline
- [ ] Документировать как запускать integration tests

---

### DEVOPS-001: Добавить security scanning в CI/CD [P2]
**Категория:** DevOps
**Оценка:** M (1 день)
**Файлы:** `.github/workflows/ci.yml`

**Описание:**
Отсутствует автоматический security scanning.

**Plan:**
1. Добавить bandit для Python security linting
2. Добавить safety check для dependencies
3. Добавить SAST scanning

**Acceptance Criteria:**
- [ ] Добавить bandit в requirements-dev.txt
- [ ] Добавить safety в requirements-dev.txt
- [ ] Обновить CI workflow:
  ```yaml
  - name: Security Scan - Bandit
    run: bandit -r backend/ -f json -o bandit-report.json

  - name: Security Scan - Safety
    run: safety check --json
  ```
- [ ] Настроить fail on high/critical findings
- [ ] Добавить badge в README
- [ ] Настроить notifications при находках
- [ ] Документировать процесс

---

### DEVOPS-002: Добавить pre-commit security hooks [P3]
**Категория:** DevOps
**Оценка:** S (2-3 часа)
**Файлы:** `.pre-commit-config.yaml`

**Описание:**
Pre-commit hooks не включают security проверки.

**Acceptance Criteria:**
- [ ] Добавить detect-secrets hook
- [ ] Добавить bandit hook
- [ ] Добавить safety hook (опционально, медленный)
- [ ] Обновить документацию
- [ ] Протестировать на локальной машине

**Пример config:**
```yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.4.0
  hooks:
    - id: detect-secrets
      args: ['--baseline', '.secrets.baseline']

- repo: https://github.com/PyCQA/bandit
  rev: 1.7.5
  hooks:
    - id: bandit
      args: ['-c', 'pyproject.toml']
```

---

## Sprint 6: Documentation & Cleanup (неделя 9)

### DOC-001: Обновить архитектурную документацию [P3]
**Категория:** Documentation
**Оценка:** M (1-2 дня)

**Acceptance Criteria:**
- [ ] Создать `docs/ARCHITECTURE.md`
- [ ] Добавить диаграммы:
  - Layered architecture
  - Data flow
  - Integration points
  - State machine
- [ ] Документировать каждый слой приложения
- [ ] Документировать ключевые паттерны (Outbox, Repository, etc.)
- [ ] Обновить README с ссылками на новую документацию

---

### DOC-002: Создать Security Guidelines [P2]
**Категория:** Documentation
**Оценка:** S (4-6 часов)

**Acceptance Criteria:**
- [ ] Создать `docs/SECURITY.md`
- [ ] Документировать:
  - Secrets management
  - Input validation best practices
  - Authentication/authorization
  - XSS prevention
  - CSRF protection
  - Rate limiting
- [ ] Добавить security checklist для code review
- [ ] Документировать процесс security incident response

---

### CODE-004: Cleanup и оптимизация [P3]
**Категория:** Code Quality
**Оценка:** M (1-2 дня)

**Acceptance Criteria:**
- [ ] Удалить неиспользуемый код (dead code)
- [ ] Удалить закомментированный код
- [ ] Оптимизировать импорты (remove unused)
- [ ] Добавить docstrings для public functions
- [ ] Стандартизировать code style
- [ ] Запустить полный code review

---

## Backlog (Future)

### FEAT-001: Implement OAuth2 для admin UI [P3]
**Категория:** Feature
**Оценка:** XL (7-10 дней)

Заменить HTTP Basic Auth на OAuth2/JWT.

---

### FEAT-002: Migrate to PostgreSQL [P3]
**Категория:** Infrastructure
**Оценка:** L (3-5 дней)

Полный переход с SQLite на PostgreSQL для production.

---

### FEAT-003: Add monitoring & alerting [P3]
**Категория:** DevOps
**Оценка:** L (4-5 дней)

Prometheus + Grafana для метрик и алертов.

---

### PERF-001: Add caching layer [P3]
**Категория:** Performance
**Оценка:** M (2-3 дня)

Redis caching для часто запрашиваемых данных (cities, templates).

---

## Метрики и отслеживание

### Sprint 0 (Немедленно)
- **Задач:** 3 (SEC-001, SEC-002, SEC-003)
- **Story Points:** ~S-M
- **Приоритет:** P0
- **Длительность:** 1 день

### Sprint 1 (Неделя 1)
- **Задач:** 5 (BUG-001, BUG-002, SEC-004, SEC-005, ARCH-001)
- **Story Points:** ~XL
- **Приоритет:** P0-P1
- **Длительность:** 1 неделя

### Sprint 2 (Неделя 2-3)
- **Задач:** 2 (ARCH-002, ARCH-003)
- **Story Points:** ~L-XL
- **Приоритет:** P1-P2
- **Длительность:** 2 недели

### Sprint 3 (Неделя 4-5)
- **Задач:** 4 (SEC-006, CODE-001, CODE-002, CODE-003)
- **Story Points:** ~XL
- **Приоритет:** P1-P2
- **Длительность:** 2 недели

### Sprint 4 (Неделя 6)
- **Задач:** 3 (DB-001, DB-002, DB-003)
- **Story Points:** ~M-L
- **Приоритет:** P1-P2
- **Длительность:** 1 неделя

### Sprint 5 (Неделя 7-8)
- **Задач:** 4 (TEST-001, TEST-002, DEVOPS-001, DEVOPS-002)
- **Story Points:** ~XL
- **Приоритет:** P2-P3
- **Длительность:** 2 недели

### Sprint 6 (Неделя 9)
- **Задач:** 3 (DOC-001, DOC-002, CODE-004)
- **Story Points:** ~M
- **Приоритет:** P2-P3
- **Длительность:** 1 неделя

---

## Итого

**Всего задач:** 27 + 4 в backlog = 31
**Общая длительность:** ~9 недель (2+ месяца)
**Критических задач (P0):** 3
**Высокоприоритетных (P1):** 10
**Среднеприоритетных (P2):** 11
**Низкоприоритетных (P3):** 7

---

## Рекомендации по выполнению

1. **Sprint 0 - сделать сегодня же** (security critical)
2. **Sprint 1 - начать немедленно** после Sprint 0
3. **Sprints 2-4** можно распараллелить между командой
4. **Sprints 5-6** выполнять параллельно с новыми features

**ВАЖНО:** После каждого спринта проводить retrospective и adjustments!

---

**Создано:** 2025-11-04
**Обновлено:** 2025-11-04
**Версия:** 1.0
