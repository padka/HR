# 🔌 Dashboard Backend Integration — Summary

## 📋 Краткое резюме

Premium Dashboard полностью интегрирован с реальными данными из PostgreSQL/SQLite через SQLAlchemy ORM. Все хардкод-данные заменены на динамические запросы из БД с graceful fallback для пустых таблиц.

---

## ✅ Что сделано

### 1. Анализ структуры БД (Models)

**Изучены модели**:
- `Recruiter` — рекрутёры (поле `active`)
- `City` — города (поле `active`)
- `Slot` — слоты для интервью (статусы: FREE, PENDING, BOOKED, CONFIRMED_BY_CANDIDATE, CANCELED)
- `User` — кандидаты (поле `candidate_status`, `last_activity`)
- `TestResult` — результаты тестов

**Файлы**:
- `backend/domain/models.py` — основные модели (Recruiter, City, Slot)
- `backend/domain/candidates/models.py` — модели кандидатов (User, TestResult)

---

### 2. Расширение Dashboard Service

**Файл**: `backend/apps/admin_ui/services/dashboard.py`

#### Новые функции:

##### a) `get_recent_candidates(limit: int = 5)`
Получает последних кандидатов из таблицы `User`:
```python
async def get_recent_candidates(limit: int = 5) -> List[Dict[str, object]]:
    """Get recent candidates/applications for dashboard."""
    async with async_session() as session:
        stmt = (
            select(User)
            .where(User.is_active == True)
            .order_by(User.last_activity.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        users = result.scalars().all()

        # Map to dashboard format with status badges
        candidates = []
        for user in users:
            status_display = "New"
            status_class = "new"

            if user.candidate_status:
                # Map status to badge style (new, review, interview, pending)
                ...

            candidates.append({
                "id": user.id,
                "name": user.fio,
                "username": user.username or "N/A",
                "city": user.city or "Не указан",
                "date": user.last_activity.strftime("%d %b %Y"),
                "status_display": status_display,
                "status_class": status_class,  # For CSS class
            })

        return candidates
```

**Возвращает**:
```python
[
    {
        "id": 123,
        "name": "Иван Иванов",
        "username": "ivan_dev",
        "city": "Москва",
        "date": "24 ноя 2025",
        "status_display": "Interview",
        "status_class": "interview"  # → status-badge--interview
    },
    ...
]
```

##### b) `get_upcoming_interviews(limit: int = 5)`
Получает предстоящие интервью из `Slot` с JOIN к `Recruiter` и `City`:
```python
async def get_upcoming_interviews(limit: int = 5) -> List[Dict[str, object]]:
    """Get upcoming interviews (booked slots) for dashboard."""
    now = datetime.now(timezone.utc)
    tomorrow_end = now + timedelta(days=2)  # Today + tomorrow

    async with async_session() as session:
        stmt = (
            select(Slot, Recruiter, City)
            .join(Recruiter, Slot.recruiter_id == Recruiter.id)
            .outerjoin(City, Slot.city_id == City.id)
            .where(
                and_(
                    or_(
                        Slot.status == SlotStatus.BOOKED,
                        Slot.status == SlotStatus.CONFIRMED_BY_CANDIDATE
                    ),
                    Slot.start_utc >= now,
                    Slot.start_utc <= tomorrow_end
                )
            )
            .order_by(Slot.start_utc.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

        interviews = []
        for slot, recruiter, city in rows:
            start_time = slot.start_utc.astimezone(timezone.utc)
            end_time = start_time + timedelta(minutes=slot.duration_min)

            # Determine platform icon
            platform = "📹 Zoom" if recruiter.telemost_url else "☎️ Телефон"

            interviews.append({
                "id": slot.id,
                "time": f"⏰ {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}",
                "candidate_name": slot.candidate_fio or "Кандидат",
                "position": f"{slot.purpose.title()} — {city.name if city else 'Interview'}",
                "platform": platform,
                "recruiter_name": recruiter.name,
            })

        return interviews
```

**Возвращает**:
```python
[
    {
        "id": 456,
        "time": "⏰ 10:00 - 11:00",
        "candidate_name": "Алексей Иванов",
        "position": "Interview — Москва",
        "platform": "📹 Zoom",
        "recruiter_name": "Мария Петрова"
    },
    ...
]
```

---

### 3. Обновление Router

**Файл**: `backend/apps/admin_ui/routers/dashboard.py`

**Изменения**:
```python
from backend.apps.admin_ui.services.dashboard import (
    dashboard_counts,
    get_recent_candidates,      # NEW
    get_upcoming_interviews,    # NEW
)

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    counts = await dashboard_counts()

    # NEW: Get dashboard data
    recent_candidates = await get_recent_candidates(limit=5)
    upcoming_interviews = await get_upcoming_interviews(limit=3)

    # ... bot integration logic ...

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "counts": counts,
            "recent_candidates": recent_candidates,      # NEW
            "upcoming_interviews": upcoming_interviews,  # NEW
            "recruiters": recruiters,
            "cities": cities,
            "bot_status": bot_status,
        },
    )
```

---

### 4. Интеграция в HTML Template

**Файл**: `backend/apps/admin_ui/templates/index.html`

#### a) Recent Applications Table

**Было** (хардкод):
```html
<tbody>
  <tr>
    <td>
      <div class="candidate-name">Алексей Иванов</div>
      <div class="candidate-position">Python Developer</div>
    </td>
    <td>Senior Python Developer</td>
    <td>22 ноя 2025</td>
    <td>
      <span class="status-badge status-badge--new">
        <span class="status-badge__dot"></span>
        New
      </span>
    </td>
  </tr>
  <!-- ... 4 more hardcoded rows ... -->
</tbody>
```

**Стало** (Jinja2 loop):
```html
<tbody>
  {% if recent_candidates %}
    {% for candidate in recent_candidates %}
  <tr>
    <td>
      <div class="candidate-name">{{ candidate.name }}</div>
      <div class="candidate-position">@{{ candidate.username }}</div>
    </td>
    <td>{{ candidate.city }}</td>
    <td>{{ candidate.date }}</td>
    <td>
      <span class="status-badge status-badge--{{ candidate.status_class }}">
        <span class="status-badge__dot"></span>
        {{ candidate.status_display }}
      </span>
    </td>
  </tr>
    {% endfor %}
  {% else %}
  <tr>
    <td colspan="4" style="text-align: center; padding: 40px; color: var(--muted);">
      Нет данных о кандидатах
    </td>
  </tr>
  {% endif %}
</tbody>
```

**Особенности**:
- ✅ Динамический CSS class: `status-badge--{{ candidate.status_class }}`
- ✅ Graceful fallback: если `recent_candidates` пуст → "Нет данных о кандидатах"
- ✅ Сохранены все CSS-классы для анимаций

---

#### b) Upcoming Interviews List

**Было** (хардкод):
```html
<div class="interview-list">
  <div class="interview-item">
    <div class="interview-item__time">⏰ 10:00 - 11:00</div>
    <div class="interview-item__candidate">Алексей Иванов</div>
    <div class="interview-item__position">Python Developer — Техническое интервью</div>
    <div class="interview-item__meta">
      <span class="interview-item__meta-badge">📹 Zoom</span>
      <span class="interview-item__meta-badge">👤 Иван Смирнов</span>
    </div>
  </div>
  <!-- ... 2 more hardcoded items ... -->
</div>
```

**Стало** (Jinja2 loop):
```html
<div class="interview-list">
  {% if upcoming_interviews %}
    {% for interview in upcoming_interviews %}
  <div class="interview-item">
    <div class="interview-item__time">{{ interview.time }}</div>
    <div class="interview-item__candidate">{{ interview.candidate_name }}</div>
    <div class="interview-item__position">{{ interview.position }}</div>
    <div class="interview-item__meta">
      <span class="interview-item__meta-badge">{{ interview.platform }}</span>
      <span class="interview-item__meta-badge">👤 {{ interview.recruiter_name }}</span>
    </div>
  </div>
    {% endfor %}
  {% else %}
  <div style="text-align: center; padding: 40px; color: var(--muted);">
    Нет запланированных интервью на сегодня
  </div>
  {% endif %}
</div>
```

**Особенности**:
- ✅ Иконки платформ из БД: "📹 Zoom", "☎️ Телефон", "👋 Intro"
- ✅ Graceful fallback: если нет интервью → "Нет запланированных интервью"
- ✅ Все hover-эффекты сохранены

---

## 🎯 Бизнес-логика

### Status Mapping (Кандидаты)

```python
if "interview" in status_str.lower():
    status_display = "Interview"
    status_class = "interview"  # → status-badge--interview (фиолетовый)

elif "test" in status_str.lower() or "review" in status_str.lower():
    status_display = "Review"
    status_class = "review"     # → status-badge--review (синий)

elif "pending" in status_str.lower() or "waiting" in status_str.lower():
    status_display = "Pending"
    status_class = "pending"    # → status-badge--pending (жёлтый)

else:
    status_display = "New"
    status_class = "new"        # → status-badge--new (зелёный)
```

### Platform Detection (Интервью)

```python
if slot.purpose == "intro":
    platform = "👋 Intro"
elif recruiter.telemost_url:
    platform = "📹 Zoom"
else:
    platform = "☎️ Телефон"
```

---

## 🛡️ Graceful Fallbacks

### Пустая БД → UI не ломается

**Кандидаты**: Если `recent_candidates` пуст:
```html
<tr>
  <td colspan="4" style="text-align: center; padding: 40px; color: var(--muted);">
    Нет данных о кандидатах
  </td>
</tr>
```

**Интервью**: Если `upcoming_interviews` пуст:
```html
<div style="text-align: center; padding: 40px; color: var(--muted);">
  Нет запланированных интервью на сегодня
</div>
```

**KPI Метрики**: Уже имели fallback в `dashboard_counts()`:
```python
return {
    "recruiters": rec_count or 0,
    "cities": city_count or 0,
    "slots_total": total,
    # ...
}
```

---

## 📊 SQL Queries (Generated by SQLAlchemy)

### Recent Candidates
```sql
SELECT users.id, users.fio, users.username, users.city, users.last_activity, users.candidate_status
FROM users
WHERE users.is_active = true
ORDER BY users.last_activity DESC
LIMIT 5
```

### Upcoming Interviews
```sql
SELECT slots.*, recruiters.*, cities.*
FROM slots
JOIN recruiters ON slots.recruiter_id = recruiters.id
LEFT OUTER JOIN cities ON slots.city_id = cities.id
WHERE (
    slots.status = 'booked' OR slots.status = 'confirmed_by_candidate'
)
AND slots.start_utc >= :now
AND slots.start_utc <= :tomorrow_end
ORDER BY slots.start_utc ASC
LIMIT 3
```

---

## 🔧 Настройки

### Изменить количество отображаемых кандидатов

**В роутере** (`backend/apps/admin_ui/routers/dashboard.py`):
```python
recent_candidates = await get_recent_candidates(limit=10)  # Было: 5
```

### Изменить период интервью

**В сервисе** (`backend/apps/admin_ui/services/dashboard.py`):
```python
tomorrow_end = now + timedelta(days=7)  # Показать интервью на неделю вперёд
```

---

## 🚀 Тестирование

### 1. С данными в БД
```bash
python scripts/dev_server.py
# Открыть http://localhost:8000/
# ✅ Таблица кандидатов заполнена
# ✅ Список интервью отображается
# ✅ Все анимации работают
```

### 2. С пустой БД
```bash
# Очистить таблицы users и slots (для теста)
# ✅ Таблица показывает "Нет данных о кандидатах"
# ✅ Интервью показывают "Нет запланированных интервью"
# ✅ Дашборд не падает, UI корректен
```

### 3. Проверка синтаксиса
```bash
.venv/bin/python -m py_compile backend/apps/admin_ui/services/dashboard.py
.venv/bin/python -m py_compile backend/apps/admin_ui/routers/dashboard.py
# ✅ Нет ошибок
```

---

## 📂 Изменённые файлы

```
backend/apps/admin_ui/
├── services/
│   └── dashboard.py ............................ Добавлены 2 функции (get_recent_candidates, get_upcoming_interviews)
│
├── routers/
│   └── dashboard.py ............................ Вызов новых функций + передача в template
│
└── templates/
    └── index.html .............................. Jinja2 циклы для candidates и interviews
```

---

## 🏆 Достижения

✅ **Динамические данные** — все хардкод заменён на БД
✅ **Graceful fallbacks** — UI не ломается при пустой БД
✅ **Сохранены эффекты** — все CSS-классы и `data-*` атрибуты на месте
✅ **Type-safe** — SQLAlchemy ORM с typed queries
✅ **Efficient queries** — JOINы вместо N+1
✅ **Clean code** — функции < 50 строк, читаемая логика

---

## 🔄 Как добавить новые поля

### Пример: Добавить телефон кандидата

#### 1. Расширить сервис
```python
candidates.append({
    "id": user.id,
    "name": user.fio,
    "username": user.username or "N/A",
    "phone": user.phone or "Не указан",  # NEW
    "city": user.city or "Не указан",
    # ...
})
```

#### 2. Обновить шаблон
```html
<div class="candidate-name">{{ candidate.name }}</div>
<div class="candidate-position">@{{ candidate.username }}</div>
<div class="candidate-phone">📞 {{ candidate.phone }}</div>  <!-- NEW -->
```

---

## 📞 Поддержка

**Проблемы с интеграцией?**
1. Проверить логи сервера: `.venv/bin/uvicorn backend.apps.admin_ui.app:app --reload`
2. Проверить консоль браузера (F12) → Network tab
3. Проверить, что БД подключена: `backend/core/db.py`

**Вопросы по запросам?**
- Добавить `echo=True` в SQLAlchemy engine для просмотра SQL-запросов
- Использовать `session.scalar(select(func.count()).select_from(Model))` для подсчётов

---

**Проект**: RecruitSmart Admin Panel
**Интеграция**: Backend → Frontend (FastAPI + Jinja2)
**ORM**: SQLAlchemy 2.0+
**База данных**: PostgreSQL/SQLite
**Версия**: 2.1.0
**Дата**: 24 ноября 2025

**🔌 Дашборд полностью интегрирован с БД!**
