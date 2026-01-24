# PROMPT ДЛЯ АГЕНТА — Priority 3: Dashboard (RecruitSmart Admin SPA)

Ты — ведущий инженер миграции. Продолжаешь перевод RecruitSmart Admin с Jinja на React/TSX SPA. Работай строго по плану в `docs/migration-map.md`.

## Контекст
- Backend: FastAPI (`backend/apps/admin_ui/`)
- SPA: React 18 + TypeScript + Vite (`frontend/app/`)
- Build output: `frontend/dist/` → монтируется на `/app/*`
- API client: `src/api/client.ts` (`apiFetch` + React Query)
- Router: TanStack Router (`src/app/main.tsx`)
- Auth: `RoleGuard`, principal через `/api/profile`

✅ Priority 1 и 2 завершены: Candidate + Slots flows.  
Текущий приоритет — **Priority 3: Dashboard**.

---

## Задачи Priority 3

### 1) Funnel Chart
- API: `GET /api/dashboard/summary` (counts по статусам)
- UI: funnel (горизонтальный/вертикальный)
- Показывать % конверсии между шагами
- Клик по сегменту → переход на `/app/candidates?status=<slug>`

### 2) Calendar View
- API: `GET /api/dashboard/calendar?date=YYYY-MM-DD&days=14`
- UI: сетка дней (FREE/BOOKED/PENDING)
- Клик по дню → `/app/slots?date=<date>`

### 3) Weekly KPIs
- Метрики: новые кандидаты, проведённые интервью, конверсия
- Опционально: сравнение с прошлой неделей

### 4) Filters
- Date range picker
- Recruiter dropdown (админ‑only)

---

## Файлы для правок
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `backend/apps/admin_ui/routers/api.py` (если нужны новые endpoints)

---

## Правила реализации
- TypeScript strict
- React Query для fetching
- Без сторонних UI‑библиотек
- Стили — только через CSS tokens (`theme/tokens.ts`)
- Любые новые endpoints должны быть backward‑compatible

---

## Порядок действий (обязательный)
1) Прочитать текущий `dashboard.tsx`
2) Проверить существование `/api/dashboard/summary` и `/api/dashboard/calendar`
3) Реализовать Funnel
4) Реализовать Calendar
5) Добавить KPI
6) Добавить фильтры
7) Обновить `docs/migration-map.md`
8) Записать решения в Decision Log
9) Добавить запись в `docs/frontend-migration-log.md`

---

## Тестирование
После каждого этапа запускать:
```
npm --prefix frontend/app run build
```
Сборка должна завершиться с exit code 0.

---

## Критерии готовности Priority 3
- [ ] Funnel показывает реальные данные
- [ ] Calendar отображает слоты по дням
- [ ] KPIs видны
- [ ] Фильтры работают
- [ ] Build успешен
- [ ] `migration-map.md` обновлён

---

## После Priority 3
Следующий приоритет: **Priority 4 — Admin CRUD Parity**  
(Recruiters: inline deactivation, Cities: inline actions, Templates: unified editor, Questions: create/clone, Message templates: history UI)

---

## Формат отчёта агента после итерации
1) Что сделано  
2) Что осталось  
3) Какие файлы изменены  
4) Какие ошибки пойманы + где зафиксированы  
5) Следующий шаг
