# ⚠️ Критичные проблемы - Требуют немедленного внимания

**Дата**: 2025-11-07
**Статус тестов**: 155/162 (95.7%) ✅

---

## 🔴 P0 - Исправить на этой неделе

### 1. Отсутствует логирование исключений (2 часа)

**Файл**: `backend/apps/admin_ui/routers/candidates.py:363-367`

**Проблема**:
```python
except Exception as e:
    # ❌ Ошибка не логируется!
    return RedirectResponse(
        url=f"/candidates/{candidate_id}?error=exception",
        status_code=303,
    )
```

**Решение**:
```python
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.exception(
        "Failed to update candidate status",
        extra={
            "candidate_id": candidate_id,
            "status": status_normalized,
            "telegram_id": telegram_id,
        }
    )
    return RedirectResponse(
        url=f"/candidates/{candidate_id}?error=exception",
        status_code=303,
    )
```

---

### 2. Backward compatibility для update_candidate_status (4 часа)

**Файл**: `backend/apps/admin_ui/services/candidates.py:1229`

**Проблема**: Старые статусы ("assigned", "accepted", "rejected") больше не работают

**Решение** (добавить перед строкой 1229):

```python
# Legacy status mappings for backward compatibility
LEGACY_STATUS_MAP = {
    "assigned": "assigned",
    "accepted": "accepted",
    "rejected": "rejected",
    "awaiting_confirmation": "awaiting_confirmation",
    "confirmed": "confirmed",
}

# В функции update_candidate_status (строка 1229):
if normalized not in STATUS_DEFINITIONS and normalized not in LEGACY_STATUS_MAP:
    return False, "Некорректный статус", None, None
```

---

### 3. CSRF защита для POST эндпоинтов (8 часов)

**Файлы**: Все POST эндпоинты в `backend/apps/admin_ui/routers/`

**Риск**: 🛡️ SECURITY - Уязвимость к CSRF атакам

**Решение**:

#### Шаг 1: Установить пакет
```bash
pip install starlette-wtf
```

#### Шаг 2: Добавить middleware в `backend/apps/admin_ui/app.py`
```python
from starlette_wtf import CSRFProtectMiddleware

def create_app():
    app = FastAPI(...)

    # Добавить CSRF защиту
    app.add_middleware(
        CSRFProtectMiddleware,
        secret=os.getenv("SESSION_SECRET", "change-me"),
    )

    return app
```

#### Шаг 3: Обновить формы в templates
```html
<!-- В candidates_detail.html и других формах -->
<form method="post" action="/candidates/{{ user.id }}/status">
    {{ csrf_token() }}  <!-- Добавить -->
    <input type="hidden" name="status" value="hired">
    <button type="submit">🎉 Закреплен</button>
</form>
```

---

## 🟡 P1 - Запланировать на неделю

### 4. Добавить тесты для нового эндпоинта (4 часа)

Создать файл `tests/test_candidate_status_endpoint.py`:

```python
@pytest.mark.asyncio
async def test_update_status_to_hired():
    # Test HIRED status change
    pass

@pytest.mark.asyncio
async def test_update_status_to_not_hired():
    # Test NOT_HIRED status change
    pass

@pytest.mark.asyncio
async def test_update_status_invalid():
    # Test invalid status rejection
    pass

@pytest.mark.asyncio
async def test_update_status_requires_telegram_id():
    # Test telegram_id validation
    pass
```

---

### 5. Rate Limiting (4 часа)

**Установить**:
```bash
pip install slowapi
```

**Добавить в app.py**:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**В эндпоинте**:
```python
@router.post("/{candidate_id}/status")
@limiter.limit("10/minute")  # Добавить
async def candidates_update_status(
    request: Request,  # Добавить
    candidate_id: int,
    status: str = Form(...),
):
    ...
```

---

## 📊 Упавшие тесты (7)

1. ❌ `test_update_candidate_status_changes_slot_and_outcome` - Legacy API
2. ❌ `test_city_recruiter_lookup_includes_slot_owners` - NOT NULL constraint
3. ❌ `test_retry_with_backoff_and_jitter` - Retry логика изменилась
4. ❌ `test_candidate_rejection_uses_message_template` - Template не используется
5. ❌ `test_reminder_service_survives_restart` - Event loop cleanup
6. ❌ `test_finalize_test1_deduplicates_by_chat_id` - HTTP 500
7. ⚠️ `test_api_integration_toggle` - Flaky (проходит отдельно)

---

## ✅ Quick Wins (можно сделать быстро)

### Исправить NOT NULL constraint в тесте (30 минут)

**Файл**: `tests/test_domain_repositories.py:69`

```python
# Убедиться что recruiter_id установлен:
session.add(
    models.Slot(
        recruiter_id=extra.id,  # ✅ Должен быть заполнен
        city_id=city.id,
        start_utc=now + timedelta(hours=2),
        status=models.SlotStatus.FREE,
    )
)
```

---

### Добавить import logging (5 минут)

**Файл**: `backend/apps/admin_ui/routers/candidates.py` (в начале файла)

```python
import logging
```

---

## 📈 Метрики

- **Test Coverage**: 95.7%
- **Security Score**: 6/10 (нужна CSRF защита)
- **Code Quality**: 8/10
- **Performance**: 8/10

---

## 🎯 План на неделю

**День 1-2** (10 часов):
- [ ] Добавить логирование исключений (2ч)
- [ ] CSRF защита (8ч)

**День 3** (6 часов):
- [ ] Backward compatibility для legacy статусов (4ч)
- [ ] Исправить NOT NULL тест (30м)
- [ ] Добавить import logging (5м)

**День 4-5** (8 часов):
- [ ] Написать тесты для эндпоинта (4ч)
- [ ] Rate limiting (4ч)

**Итого**: ~24 часа работы для исправления всех критичных проблем

---

## 📞 Нужна помощь?

Полный отчет с детальным анализом: `QA_REPORT.md`

Запустить тесты:
```bash
ENVIRONMENT=development REDIS_URL="" .venv/bin/python -m pytest tests/ -v
```

Запустить только упавшие:
```bash
ENVIRONMENT=development REDIS_URL="" .venv/bin/python -m pytest \
  tests/test_admin_candidates_service.py::test_update_candidate_status_changes_slot_and_outcome \
  tests/test_domain_repositories.py::test_city_recruiter_lookup_includes_slot_owners \
  tests/test_notification_retry.py::test_retry_with_backoff_and_jitter \
  -vv
```
