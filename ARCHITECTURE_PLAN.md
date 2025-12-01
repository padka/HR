# План архитектурных изменений: RecruitSmart UI/UX Upgrade

## Цели (Северная звезда)
- Снизить когнитивную нагрузку на кандидатов и рекрутеров
- Повысить конверсию в ключевые действия (бронирование, подтверждение, доходимость)
- Единообразный premium-визуал сообщений
- Удобный WebApp для управления бронированиями

## Текущее состояние

### Что есть:
- ✅ aiogram 3.10 bot
- ✅ FastAPI admin_ui
- ✅ TemplateProvider с DB-backed шаблонами
- ✅ Jinja2==3.1.4 (используется для HTML админки)
- ✅ SQLAlchemy models, Alembic migrations
- ✅ Redis для state store
- ✅ Базовая система metrics

### Проблемы:
- ❌ Шаблоны сообщений используют примитивный `.format()` без компонентности
- ❌ Нет единого стиля (эмодзи, даты, переносы)
- ❌ Хардкод форматов дат/времени
- ❌ Нет WebApp API
- ❌ Нет initData validation для Telegram WebApp
- ❌ Недостаточно structured events для аналитики

---

## Итерация 1: Компонентная система сообщений + Базовый WebApp API

### A) Telegram Messages "дорого-богато"

#### 1.1 Внедрить Jinja2 для сообщений бота

**Структура директорий:**
```
backend/apps/bot/
  templates_jinja/           # Новая папка для Jinja2
    blocks/                  # Компоненты
      header.j2              # Заголовок с иконкой
      info_row.j2            # Строка инфо (дата/время/адрес)
      checklist.j2           # Чек-лист с ✓/□
      footer_hint.j2         # Подсказка внизу
      actions.j2             # Inline кнопки
      datetime.j2            # Макрос форматирования даты
    messages/                # Полные сообщения
      interview_confirmed.j2
      reminder_2h.j2
      reminder_3h.j2
      reminder_6h.j2
      intro_day_invitation.j2
      intro_day_preparation.j2
      reschedule_prompt.j2
      no_show_gentle.j2
```

**Новый модуль:** `backend/apps/bot/jinja_renderer.py`
- Инициализация Jinja2 Environment
- Глобальные фильтры: `format_datetime`, `format_date`, `format_time`
- Макросы для компонентов
- Интеграция с TemplateProvider

#### 1.2 MessageStyleGuide.md

Создать `backend/apps/bot/MessageStyleGuide.md`:
- Правила длины строк (макс 60 символов)
- Эмодзи-маркеры (📅 дата, 🕐 время, 📍 адрес, 💬 формат, ✨ важное)
- Формат даты/времени: **Пн, 12 дек • 14:30 (МСК)**
- Правила переносов (один логический блок = один параграф)
- Запрет на "простыни" (макс 3-4 блока)
- Tone of voice: дружелюбно, но профессионально

#### 1.3 Реализовать 7 обязательных шаблонов

1. `interview_confirmed.j2` - подтверждение записи на созвон
2. `reminder_6h.j2` - напоминание за 6 часов
3. `reminder_3h.j2` - напоминание за 3 часа
4. `reminder_2h.j2` - напоминание за 2 часа + ссылка
5. `interview_preparation.j2` - инструкция перед созвоном (чек-лист)
6. `interview_success_introday.j2` - итог созвона + запись на ОД
7. `intro_day_invitation.j2` - инструкция на ОД (адрес/контакт/что взять)
8. `reschedule_prompt.j2` - перенос/отмена
9. `no_show_gentle.j2` - "не дозвонились / не пришёл" (бережно)

**Формат даты единый:**
- Функция `format_local_dt(dt_utc, tz_name)` → "Пн, 12 дек • 14:30 (МСК)"
- Короткий формат: "12.12 • 14:30"

#### 1.4 Миграция TemplateProvider на Jinja2

- Расширить `TemplateProvider.render()` для поддержки Jinja2
- Fallback на старый `.format()` для обратной совместимости
- Добавить флаг `use_jinja: bool` в DB schema (новая миграция)
- Cache compiled Jinja2 templates

### B) Telegram WebApp API (Backend)

#### 2.1 initData validation

**Новый модуль:** `backend/apps/admin_api/webapp/auth.py`
```python
from fastapi import Depends, HTTPException, Header
import hmac
import hashlib

async def validate_telegram_webapp_init_data(
    x_telegram_init_data: str = Header(...),
    bot_token: str = Depends(get_bot_token)
) -> TelegramUser:
    # Проверка подписи initData
    # Парсинг user data
    # Возврат TelegramUser(user_id, username, ...)
```

#### 2.2 WebApp Endpoints

**Новый роутер:** `backend/apps/admin_api/routers/webapp.py`

**Candidate endpoints:**
```python
GET  /api/webapp/me                        # Инфо о кандидате
GET  /api/webapp/slots?city_id=&from=&to=  # Доступные слоты
POST /api/webapp/booking                   # Забронировать {slot_id}
POST /api/webapp/reschedule                # Перенести {booking_id, new_slot_id}
POST /api/webapp/cancel                    # Отменить {booking_id, reason?}
GET  /api/webapp/intro_day?city_id=        # Инфо об ОД
GET  /api/webapp/calendar_ics/{booking_id} # .ics файл
```

**Recruiter endpoints (опционально в MVP):**
```python
GET  /api/webapp/recruiter/dashboard       # Сводка
GET  /api/webapp/recruiter/candidates      # Список кандидатов
POST /api/webapp/recruiter/candidate/note  # Добавить заметку
```

#### 2.3 RBAC для WebApp

- Middleware для проверки роли (candidate vs recruiter)
- Isolate data by city_id (recruiter видит только свой периметр)
- Rate limiting (опционально, но желательно)

### C) Analytics Events

**Новая таблица:** `analytics_events`
```sql
CREATE TABLE analytics_events (
    id SERIAL PRIMARY KEY,
    event_name VARCHAR(100) NOT NULL,
    user_id BIGINT,
    candidate_id INT,
    city_id INT,
    slot_id INT,
    booking_id INT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_events_name ON analytics_events(event_name);
CREATE INDEX idx_events_candidate ON analytics_events(candidate_id);
CREATE INDEX idx_events_created ON analytics_events(created_at);
```

**События для логирования:**
- `slot_viewed`, `slot_booked`, `slot_rescheduled`, `slot_canceled`
- `reminder_sent_6h`, `reminder_sent_3h`, `reminder_sent_2h`
- `reminder_clicked_confirm`, `map_opened`, `calendar_downloaded`
- `no_show_call`, `no_show_introday`, `arrived_confirmed`

**Новый модуль:** `backend/domain/analytics.py`
```python
async def log_event(
    event_name: str,
    user_id: Optional[int] = None,
    candidate_id: Optional[int] = None,
    metadata: Optional[Dict] = None
) -> None:
    # Insert в analytics_events
```

---

## Итерация 2: Telegram Mini App Frontend (MVP)

### Frontend Stack
- Next.js 14 (App Router)
- Tailwind CSS + shadcn/ui
- Telegram WebApp SDK (@twa-dev/sdk)
- React Query для API calls

### Структура проекта
```
webapp/
  app/
    candidate/
      page.tsx          # Home (next step)
      slots/page.tsx    # Список слотов
      booking/[id]/page.tsx  # Детали брони
    recruiter/
      page.tsx          # Dashboard
      candidates/page.tsx
```

### Экраны кандидата:
1. **Home** - статус текущей брони, next step
2. **Slots** - календарь/список слотов, фильтр по городу
3. **Booking confirmation** - подтверждение с чек-листом
4. **Preparation checklist** - что взять, как подготовиться
5. **Reschedule/Cancel** - перенос/отмена

### UX требования:
- Поддержка Telegram theme (light/dark via `window.Telegram.WebApp.themeParams`)
- Большие кнопки (min 44px height)
- После действия: success toast + `window.Telegram.WebApp.close()`
- Deep links: `tg://resolve?domain=bot&start=webapp_slots`
- "Добавить в календарь": генерация .ics через backend endpoint

### Recruiter экраны (опц.):
1. **Dashboard** - сегодняшние созвоны, статистика
2. **Candidates list** - фильтры, search
3. **Candidate card** - действия, заметки

---

## Итерация 3 (Опционально): PNG карточки

- HTML → PNG через Playwright
- Кеширование в Redis/S3
- Endpoint: `GET /api/bot/card_image/{booking_id}.png`

---

## Тестирование

### Unit тесты:
- `tests/test_jinja_renderer.py` - рендер компонентов
- `tests/test_webapp_auth.py` - initData validation
- `tests/test_webapp_api.py` - все endpoints

### E2E тесты:
- `tests/e2e/test_webapp_booking_flow.py` (Playwright)
- Smoke: открыть WebApp → забронировать → перенести → отменить

### Регресс:
- Все существующие тесты должны проходить
- No breaking changes в bot handlers

---

## Миграции БД

### Новая миграция: `0031_webapp_and_analytics.py`
```python
# 1. Добавить use_jinja в message_templates
op.add_column('message_templates', sa.Column('use_jinja', sa.Boolean(), default=False))

# 2. Создать analytics_events
op.create_table('analytics_events', ...)

# 3. Индексы
op.create_index('idx_events_name', 'analytics_events', ['event_name'])
op.create_index('idx_events_candidate', 'analytics_events', ['candidate_id'])
```

---

## Конфигурация

### Новые env переменные:
```bash
# .env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBAPP_ENABLED=true
TELEGRAM_WEBAPP_URL=https://webapp.example.com
JINJA_TEMPLATES_DIR=backend/apps/bot/templates_jinja
```

---

## Definition of Done

### Итерация 1:
- ✅ Все 7+ шаблонов переведены на Jinja2
- ✅ MessageStyleGuide.md написан
- ✅ Единый формат дат везде
- ✅ WebApp API endpoints готовы
- ✅ initData validation работает
- ✅ Analytics events логируются
- ✅ Unit тесты покрывают новый код
- ✅ Все существующие тесты зелёные
- ✅ PR открыт с понятным описанием

### Итерация 2:
- ✅ WebApp работает в Telegram light/dark
- ✅ Кандидат может забронировать/перенести/отменить
- ✅ RBAC работает корректно
- ✅ Graceful degradation без Redis
- ✅ E2E тесты проходят
- ✅ PR открыт

---

## Риски и митигации

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Breaking changes в существующих сообщениях | Средняя | Fallback на старый .format() |
| initData validation ломает auth | Низкая | Тесты + staging environment |
| Jinja2 медленнее .format() | Низкая | Кеширование compiled templates |
| WebApp не работает в старых Telegram | Средняя | Feature detection + fallback на бот |

---

## Зоны ответственности агентов

- **Tech Lead:** Этот план, координация, review PR
- **Backend Agent:** initData, webapp endpoints, analytics, миграции
- **Bot/UI Agent:** Jinja2 шаблоны, MessageStyleGuide, интеграция с TemplateProvider
- **Frontend Agent:** Next.js WebApp (Итерация 2)
- **QA Agent:** Тест-план, e2e тесты, регресс

---

## Следующие шаги

1. ✅ Создать этот план
2. Начать с Jinja2 интеграции (backend/apps/bot/jinja_renderer.py)
3. Создать MessageStyleGuide.md
4. Реализовать 1-2 шаблона как proof-of-concept
5. Добавить initData validation
6. Создать базовые WebApp endpoints
7. Добавить analytics events
8. Написать тесты
9. Открыть PR для итерации 1

**Статус:** В работе (Итерация 1)
