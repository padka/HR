# Bugfix: IntegrityError при повторном вызове reject_booking

**Дата:** 2025-11-05
**Статус:** ✅ Исправлено
**Severity:** High (Критическая ошибка в production)

---

## Описание проблемы

### Симптомы

При повторном вызове `reject_booking()` система выбрасывала:

```
IntegrityError: UNIQUE constraint failed:
outbox_notifications.type,
outbox_notifications.booking_id,
outbox_notifications.candidate_tg_id
```

### Воздействие на пользователей

- ❌ Невозможно повторно отклонить бронирование слота
- ❌ Ошибки в логах при попытке создать дубликаты уведомлений
- ❌ Потенциальная потеря уведомлений при сбоях

### Когда возникала проблема

Ошибка возникала в следующих сценариях:

1. **Повторное отклонение слота:**
   - Рекрутер отклоняет слот → создается outbox запись
   - Система обрабатывает и отправляет → status='sent'
   - Рекрутер снова отклоняет (случайно или намеренно)
   - **💥 IntegrityError** - попытка создать дубликат

2. **Retry логика:**
   - Первая попытка отклонения сохраняет запись
   - При retry попытка создать ту же запись → IntegrityError

---

## Корневая причина

### Техническая причина

В функции `add_outbox_notification()` (backend/domain/repositories.py) была следующая логика:

```python
# БЫЛО (после предыдущего исправления):
existing = await sess.scalar(
    select(OutboxNotification)
    .where(
        OutboxNotification.type == notification_type,
        OutboxNotification.booking_id == booking_id,
        OutboxNotification.candidate_tg_id == candidate_tg_id,
        OutboxNotification.status == "pending",  # ❌ ПРОБЛЕМА!
    )
    .with_for_update()
)
```

### Почему это вызывало IntegrityError

1. **Первый вызов reject_booking:**
   - Создается `OutboxNotification` с status='pending'
   - Worker обрабатывает → status='sent' ✅

2. **Второй вызов reject_booking:**
   - `add_outbox_notification()` ищет существующие записи
   - Фильтр `status == "pending"` **НЕ НАХОДИТ** запись (status='sent')
   - Пытается создать НОВУЮ запись с теми же (type, booking_id, candidate_tg_id)
   - **💥 UNIQUE constraint violation!**

### Диаграмма последовательности

```
Время  Событие                             OutboxNotification
──────────────────────────────────────────────────────────────────
T0     Рекрутер отклоняет слот             [id:1, status:pending]
T1     Worker отправляет уведомление       [id:1, status:sent] ✅
T2     Рекрутер снова отклоняет слот
T3     add_outbox_notification()
       - Ищет status='pending'
       - НЕ находит (status='sent')
       - Пытается INSERT
T4     💥 IntegrityError!                  UNIQUE constraint failed
```

---

## Решение

### Идемпотентность

Сделал метод `add_outbox_notification()` **истинно идемпотентным**:

**Идемпотентность** = вызов функции с одинаковыми параметрами всегда возвращает тот же результат.

### Код после исправления

**Файл:** `backend/domain/repositories.py:562-608`

```python
async def _add(sess) -> OutboxNotification:
    # Ищем существующую запись независимо от status (идемпотентность!)
    existing = await sess.scalar(
        select(OutboxNotification)
        .where(
            OutboxNotification.type == notification_type,
            OutboxNotification.booking_id == booking_id,
            OutboxNotification.candidate_tg_id == candidate_tg_id,
            # ✅ УБРАН фильтр по status!
        )
        .with_for_update()
    )

    if existing:
        # Если status='pending', обновляем (retry сценарий)
        if existing.status == "pending":
            if recruiter_tg_id is not None:
                existing.recruiter_tg_id = recruiter_tg_id
            if payload:
                existing.payload_json = payload
            if correlation_id:
                existing.correlation_id = correlation_id
            existing.next_retry_at = None
            existing.locked_at = None
            if existing.attempts > 0:
                existing.attempts = 0
            return existing
        else:
            # ✅ Status='sent' или 'failed' → возвращаем as-is
            # НЕ модифицируем, чтобы избежать дубликатов
            return existing

    # Нет существующей записи - создаем новую
    entry = OutboxNotification(
        booking_id=booking_id,
        type=notification_type,
        payload_json=payload,
        candidate_tg_id=candidate_tg_id,
        recruiter_tg_id=recruiter_tg_id,
        status="pending",
        attempts=0,
        created_at=now,
        locked_at=None,
        next_retry_at=None,
        correlation_id=correlation_id,
    )
    sess.add(entry)
    return entry
```

### Новая логика работы

**Сценарий 1: Первый вызов reject_booking**
```
1. add_outbox_notification() ищет существующую запись
2. Не находит
3. Создает новую с status='pending'
4. Worker обрабатывает → status='sent'
```

**Сценарий 2: Повторный вызов reject_booking**
```
1. add_outbox_notification() ищет существующую запись
2. ✅ Находит запись с status='sent'
3. ✅ Возвращает её as-is (не модифицирует!)
4. ✅ Нет IntegrityError, нет дубликатов
```

**Сценарий 3: Retry для pending записи**
```
1. add_outbox_notification() ищет существующую запись
2. Находит запись с status='pending'
3. Обновляет payload, attempts, retry_at
4. Возвращает обновленную запись
```

---

## Тестирование

### Regression Tests

**Файл:** `tests/test_outbox_deduplication.py`

#### Test 1: Идемпотентность для sent записей
```python
async def test_add_outbox_notification_is_idempotent_for_sent_entries():
    """
    Проверяет, что add_outbox_notification идемпотентна для sent записей.

    При попытке создать уведомление, которое уже существует с status='sent',
    функция должна вернуть существующую запись БЕЗ модификации.
    Это предотвращает IntegrityError и обеспечивает идемпотентность.
    """
    # 1. Создать запись
    entry1 = await add_outbox_notification(...)

    # 2. Пометить как sent
    await update_outbox_entry(entry1.id, status="sent")

    # 3. Попытка создать ту же запись
    entry2 = await add_outbox_notification(...)

    # 4. ПРОВЕРКА: Должна вернуться та же запись
    assert entry2.id == entry1.id  # ✅ Та же запись
    assert entry2.status == "sent"  # ✅ Status не изменился

    # 5. Проверка: В БД только 1 запись
    all_entries = await session.execute(select(OutboxNotification)...)
    assert len(all_entries) == 1  # ✅ Нет дубликатов
```

#### Test 2: Reuse pending записей
```python
async def test_add_outbox_notification_reuses_pending_entries():
    """
    Проверяет, что add_outbox_notification переиспользует pending записи.

    Если запись все еще pending, мы должны обновить её, а не создать дубликат.
    """
    # 1. Создать pending запись
    entry1 = await add_outbox_notification(...)

    # 2. Попытка создать ту же запись (пока pending)
    entry2 = await add_outbox_notification(...)

    # 3. ПРОВЕРКА: Должна переиспользоваться
    assert entry2.id == entry1.id
    assert entry2.status == "pending"
```

#### Test 3: Разные типы - разные записи
```python
async def test_add_outbox_notification_different_types_are_separate():
    """
    Проверяет, что разные типы уведомлений создают разные записи.
    """
    entry1 = await add_outbox_notification(type="slot_reminder", ...)
    entry2 = await add_outbox_notification(type="interview_confirmed", ...)

    # Разные типы → разные записи
    assert entry2.id != entry1.id
```

### Результаты тестов

```bash
$ pytest tests/test_outbox_deduplication.py -v

collected 3 items

test_add_outbox_notification_is_idempotent_for_sent_entries PASSED [ 33%]
test_add_outbox_notification_reuses_pending_entries PASSED        [ 66%]
test_add_outbox_notification_different_types_are_separate PASSED  [100%]

3 passed ✅
```

### Проверка связанных тестов

```bash
$ pytest tests/test_notification_retry.py -v

collected 6 items

test_retry_with_backoff_and_jitter PASSED                    [ 16%]
test_poll_once_handles_duplicate_notification_logs PASSED    [ 33%]
test_candidate_rejection_uses_message_template PASSED        [ 50%]
test_fatal_error_marks_outbox_failed PASSED                  [ 66%]
test_broker_dlq_on_max_attempts PASSED                       [ 83%]
test_broker_bootstrap_from_outbox PASSED                     [100%]

6 passed ✅
```

---

## Файлы изменены

### Modified

- **`backend/domain/repositories.py`**
  - Строки 562-608: Убран фильтр `status == "pending"` из SELECT запроса
  - Добавлена логика возврата существующих sent/failed записей as-is
  - Сохранена логика обновления для pending записей

- **`tests/test_outbox_deduplication.py`**
  - Переименован тест: `test_add_outbox_notification_is_idempotent_for_sent_entries`
  - Обновлены assertions для проверки идемпотентности
  - Добавлены проверки на отсутствие дубликатов в БД

---

## Deployment Notes

### Breaking Changes
**Нет** - обратно совместимые изменения.

### Database Changes
**Нет** - изменения только в коде.

### Configuration Changes
**Нет**

### Rollback Plan
```bash
git revert 37d6ef3
```

---

## Проверка после деплоя

### 1. Мониторинг IntegrityError

Проверить логи на отсутствие IntegrityError:

```bash
grep "IntegrityError.*outbox_notifications" app.log
# Ожидаемый результат: пустой вывод (нет ошибок)
```

### 2. Проверка дубликатов

SQL запрос для проверки дубликатов:

```sql
SELECT type, booking_id, candidate_tg_id, COUNT(*)
FROM outbox_notifications
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY type, booking_id, candidate_tg_id
HAVING COUNT(*) > 1;
```

**Ожидаемый результат:** Пустой набор (нет дубликатов)

### 3. Функциональное тестирование

**Сценарий:** Повторное отклонение слота
1. Создать слот в статусе BOOKED
2. Отклонить через админку → проверить создание outbox записи
3. **Повторно отклонить** → ✅ не должно быть ошибок
4. Проверить: в outbox только 1 запись для этого booking_id

---

## История проблемы

### Эволюция исправлений

#### Версия 1: Исходный код (до исправлений)
```python
# Нет фильтра вообще → переиспользовал sent записи
# Проблема: дублирующиеся уведомления
existing = await sess.scalar(
    select(OutboxNotification).where(...)
    # Любая запись, даже sent
)
if existing:
    existing.status = "pending"  # ❌ Ре-активация sent записей!
```

**Проблема:** Дублирующиеся CONFIRM_2H сообщения (см. BUGFIX_DUPLICATE_NOTIFICATIONS.md)

#### Версия 2: Первое исправление (commit 0ebe7f8)
```python
# Добавлен фильтр status='pending'
existing = await sess.scalar(
    select(OutboxNotification).where(
        ...,
        OutboxNotification.status == "pending",  # ✅ Только pending
    )
)
```

**Результат:** Дубликаты устранены ✅
**Новая проблема:** IntegrityError при повторных вызовах ❌

#### Версия 3: Текущее исправление (commit 37d6ef3)
```python
# Убран фильтр по status, возврат существующих as-is
existing = await sess.scalar(
    select(OutboxNotification).where(...)
    # Любая запись
)
if existing:
    if existing.status == "pending":
        # Обновляем pending
    else:
        # Возвращаем sent/failed as-is ✅
```

**Результат:**
- ✅ Нет дубликатов
- ✅ Нет IntegrityError
- ✅ Истинная идемпотентность

---

## Lessons Learned

### 1. Идемпотентность требует комплексного подхода

**Неправильно:**
```python
# Просто проверяем pending записи
if existing and existing.status == "pending":
    return existing
# Создаем новую → IntegrityError!
```

**Правильно:**
```python
# Проверяем ВСЕ записи, возвращаем существующую
if existing:
    return existing  # Идемпотентность!
# Только если НЕТ записи - создаем
```

### 2. UNIQUE constraints требуют предварительной проверки

- При наличии UNIQUE constraint на (type, booking_id, candidate_tg_id)
- Всегда делать SELECT перед INSERT
- Или использовать INSERT ... ON CONFLICT DO NOTHING

### 3. Статусы != Идентичность записи

- Идемпотентность определяется **ключевыми полями** (type, booking_id, candidate_tg_id)
- Status - это **состояние жизненного цикла**, не идентичность
- Проверка идемпотентности должна игнорировать status

### 4. Тестирование edge cases

Важно тестировать:
- ✅ Первый вызов (создание)
- ✅ Повторный вызов с pending записью
- ✅ Повторный вызов с sent записью ← **КРИТИЧНО!**
- ✅ Разные типы уведомлений

---

## Рекомендации на будущее

### Immediate
1. ✅ Деплоить в продакшн
2. ✅ Мониторить логи на IntegrityError

### Short-term
1. 📋 Добавить метрики для отслеживания повторных вызовов
2. 📋 Добавить логирование при возврате существующих записей
3. 📋 Ревью всех мест, где используется add_outbox_notification()

### Long-term
1. 📋 Рассмотреть использование UPSERT (ON CONFLICT) на уровне БД
2. 📋 Добавить distributed locking для критичных операций
3. 📋 Ввести versioning для outbox записей

---

## Связанные документы

- [BUGFIX_DUPLICATE_NOTIFICATIONS.md](./BUGFIX_DUPLICATE_NOTIFICATIONS.md) - Первое исправление (дубликаты CONFIRM_2H)
- [BUGFIX_FORM_DUPLICATION.md](./BUGFIX_FORM_DUPLICATION.md) - Дубликаты анкет
- [QA_REPORT.md](./QA_REPORT.md) - Общий QA отчет Sprint 0

---

## Commit Reference

**Commit:** `37d6ef3`
**Title:** Исправить IntegrityError: сделать add_outbox_notification идемпотентным
**Author:** Claude Code
**Date:** 2025-11-05

---

## Conclusion

**Статус:** ✅ **Исправлено и протестировано**

Проблема IntegrityError при повторных вызовах `reject_booking` полностью решена:

1. ✅ Метод `add_outbox_notification()` теперь истинно идемпотентен
2. ✅ Нет IntegrityError при повторных вызовах
3. ✅ Нет дублирующихся уведомлений
4. ✅ Comprehensive regression tests
5. ✅ Минимальные изменения кода
6. ✅ Нет breaking changes

Решение готово к продакшену.

---

**Подготовил:** Claude Code (Backend Development)
**Дата отчета:** 2025-11-05
