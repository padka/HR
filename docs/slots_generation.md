# Генерация слотов (админка /slots)

Где что живёт
- Генерация дня: `POST /slots/generate-default` → `backend/apps/admin_ui/routers/slots.py::slots_generate_default` → `services.slots.generate_default_day_slots`.
- Листинг таблицы: `GET /slots` → `routers/slots.slots_list` → `services.slots.list_slots` (фильтры по recruiter_id, status, city, date). Таблица рендерится сервером, без отдельного API.

Логика генерации
- Создаёт 24 слота: 09:00–12:00 и 13:00–18:00 с шагом 20 минут.
- Статус: `FREE`, purpose: `interview`, tz_name: город → рекрутер → `DEFAULT_TZ`.
- Город:
  - Если выбран в форме — используется этот city_id.
  - Если “Авто” — берётся первый город рекрутёра (отсортирован по имени) или `None`, если городов нет.
  - `city_id` и `candidate_city_id` ставятся одинаково.
- Времена считаются в часовой зоне tz_name, сохраняются в UTC.
- Дубликаты на тот же день/рекрутёра в том же часовом окне не создаются.

Правила листинга
- Отбираются слоты `purpose != intro_day`.
- Фильтр дата интерпретируется в `DEFAULT_TZ` и превращается в UTC-диапазон суток.
- Фильтр города — по имени города (City.name).
- Обязательные поля для отображения: recruiter_id, start_utc; city_id/название опциональны, но показываются если заданы.
