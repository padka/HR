# Caching (admin_ui perf)

Цель: уменьшить DB work на hot read endpoints и стабилизировать tail latency под нагрузкой, **без утечек данных между пользователями/ролями/скоупами**.

## Слои кэша

1. **microcache** (in-process)
- TTL секунды
- без кросс-воркер консистентности
- используется для ultra-hot reads

2. **Redis** (best-effort)
- TTL секунды
- может быть отключён/недоступен без фатала

Read-through интерфейсы:
- `backend/apps/admin_ui/perf/cache/readthrough.py`
  - `get_cached()`: read microcache → redis
  - `set_cached()`: write microcache → redis (best-effort)
  - `get_or_compute()`: read-through + single-flight fill + (опционально) SWR

## Политика ключей (security)

Ключи строятся централизованно в:
- `backend/apps/admin_ui/perf/cache/keys.py`

Правила:
1. **Никакой PII** в ключах: ФИО, телефоны, свободный текст, ссылки.
2. Если ответ персонализирован: ключ **обязан** включать principal scope (`admin/recruiter` + id).
3. Если ответ зависит от query params: нормализовать порядок/пустые значения.
4. Если endpoint ограничен городом/тенантом: ключ должен включать city/tenant scope.

Тесты безопасности кэша должны подтверждать:
- два разных пользователя не получают один и тот же cached response там, где данные персональные
- разные роли не пересекаются

## SWR (stale-while-revalidate)

Если `stale_seconds>0`:
- после истечения TTL, но до `TTL+stale_seconds`:
  - отдаём stale ответ немедленно
  - запускаем background refresh (single-flight per key)

Degraded mode:
- если запрос marked degraded (DB down) → refresh в фоне **не запускается**, отдаём stale best-effort.

## Как безопасно добавить cached endpoint

1. Определить scoping:
- shared (одинаковый для всех) или per-principal
2. Добавить key builder в `keys.py`.
3. Использовать `get_or_compute()` и политику TTL/SWR (см. `backend/apps/admin_ui/perf/cache/policy.py`).
4. Если endpoint допускается во время деградации DB:
- добавить path в allowlist `backend/apps/admin_ui/perf/degraded/allowlist.py`
5. Добавить тест на key scoping.

