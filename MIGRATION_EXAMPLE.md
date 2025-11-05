# Пример миграции на новую архитектуру

## Пример 1: Простой запрос

### ❌ Было (старый код)

```python
from backend.domain.repositories import get_active_recruiters

async def get_recruiters_list():
    try:
        recruiters = await get_active_recruiters()
        if not recruiters:
            return {"status": "empty", "data": []}

        return {
            "status": "success",
            "data": [{"id": r.id, "name": r.name} for r in recruiters]
        }
    except Exception as e:
        logger.error(f"Error getting recruiters: {e}")
        return {"status": "error", "message": str(e)}
```

### ✅ Стало (новый код)

```python
from backend.core.uow import UnitOfWork
from backend.core.result import Success, Failure, DatabaseError

async def get_recruiters_list():
    async with UnitOfWork() as uow:
        result = await uow.recruiters.get_active()

        match result:
            case Success(recruiters):
                return {
                    "status": "success",
                    "data": [{"id": r.id, "name": r.name} for r in recruiters]
                }
            case Failure(DatabaseError() as error):
                logger.error(f"Database error: {error}")
                return {"status": "error", "message": "Database error occurred"}
```

**Преимущества**:
- ✅ Явная обработка ошибок
- ✅ Типобезопасность
- ✅ Централизованное управление сессией

---

## Пример 2: Создание сущности

### ❌ Было (старый код)

```python
from backend.core.db import async_session
from backend.domain.models import Recruiter

async def create_recruiter(name: str, tg_chat_id: int):
    async with async_session() as session:
        try:
            recruiter = Recruiter(name=name, tg_chat_id=tg_chat_id, active=True)
            session.add(recruiter)
            await session.commit()
            await session.refresh(recruiter)

            return recruiter

        except IntegrityError:
            await session.rollback()
            raise ValueError("Recruiter with this Telegram ID already exists")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating recruiter: {e}")
            raise
```

### ✅ Стало (новый код)

```python
from backend.core.uow import UnitOfWork
from backend.core.result import Success, Failure, DatabaseError
from backend.domain.models import Recruiter

async def create_recruiter(name: str, tg_chat_id: int):
    async with UnitOfWork() as uow:
        recruiter = Recruiter(name=name, tg_chat_id=tg_chat_id, active=True)

        result = await uow.recruiters.add(recruiter)

        match result:
            case Success(created_recruiter):
                await uow.commit()
                return Success(created_recruiter)

            case Failure(DatabaseError(message=msg)) if "constraint" in msg.lower():
                # Constraint violation - duplicate
                return Failure(ConflictError(
                    entity_type="Recruiter",
                    message="Recruiter with this Telegram ID already exists",
                    conflicting_field="tg_chat_id"
                ))

            case Failure(error):
                logger.error(f"Error creating recruiter: {error}")
                return Failure(error)
```

**Преимущества**:
- ✅ Автоматический rollback
- ✅ Явное различие типов ошибок
- ✅ Chainable operations

---

## Пример 3: Сложная операция (множественные репозитории)

### ❌ Было (старый код)

```python
from backend.core.db import async_session
from backend.domain.models import Slot, SlotStatus
from backend.domain.repositories import get_slot, update_slot

async def book_slot(slot_id: int, telegram_id: int):
    async with async_session() as session:
        try:
            # Получаем слот
            slot = await get_slot(slot_id)
            if not slot:
                return None, "Slot not found"

            if slot.status != SlotStatus.FREE:
                return None, "Slot is not available"

            # Обновляем слот
            slot.status = SlotStatus.RESERVED
            slot.telegram_id = telegram_id

            # Создаем уведомление
            notification = NotificationLog(
                telegram_id=telegram_id,
                slot_id=slot_id,
                # ...
            )
            session.add(notification)

            await session.commit()

            return slot, None

        except Exception as e:
            await session.rollback()
            logger.error(f"Error booking slot: {e}")
            return None, str(e)
```

### ✅ Стало (новый код)

```python
from backend.core.uow import UnitOfWork
from backend.core.result import Success, Failure, NotFoundError, ValidationError
from backend.domain.models import Slot, SlotStatus, NotificationLog

async def book_slot(slot_id: int, telegram_id: int):
    async with UnitOfWork() as uow:
        # Получаем слот
        slot_result = await uow.slots.get(slot_id)

        match slot_result:
            case Failure(NotFoundError()):
                return Failure(NotFoundError(
                    entity_type="Slot",
                    entity_id=slot_id,
                    message="Slot not found"
                ))

            case Success(slot):
                # Проверяем доступность
                if slot.status != SlotStatus.FREE:
                    return Failure(ValidationError(
                        field="status",
                        message="Slot is not available",
                        value=slot.status
                    ))

                # Обновляем слот
                slot.status = SlotStatus.RESERVED
                slot.telegram_id = telegram_id

                update_result = await uow.slots.update(slot)
                if update_result.is_failure():
                    return update_result

                # Создаем уведомление
                notification = NotificationLog(
                    telegram_id=telegram_id,
                    slot_id=slot_id,
                    # ...
                )

                notify_result = await uow.notifications.add(notification)
                if notify_result.is_failure():
                    return notify_result

                # Коммитим все изменения атомарно
                await uow.commit()

                return Success(slot)

            case _:
                return slot_result  # Пробрасываем другие ошибки
```

**Преимущества**:
- ✅ Атомарные операции
- ✅ Явная обработка каждого типа ошибки
- ✅ Автоматический rollback при ошибке
- ✅ Все операции в одной транзакции

---

## Пример 4: Batch операции

### ❌ Было (старый код)

```python
from backend.core.db import async_session
from backend.domain.models import User

async def create_users_batch(users_data: list[dict]):
    created = []
    errors = []

    for user_data in users_data:
        async with async_session() as session:
            try:
                user = User(**user_data)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                created.append(user)
            except Exception as e:
                errors.append({"data": user_data, "error": str(e)})

    return created, errors
```

**Проблемы**:
- ❌ N транзакций (медленно)
- ❌ Partial success (часть создастся, часть нет)
- ❌ Нет rollback при ошибке

### ✅ Стало (новый код)

```python
from backend.core.uow import UnitOfWork
from backend.core.result import Success, Failure, collect_results
from backend.domain.candidates.models import User

async def create_users_batch(users_data: list[dict]):
    async with UnitOfWork() as uow:
        results = []

        # Добавляем всех пользователей
        for user_data in users_data:
            user = User(**user_data)
            result = await uow.users.add(user)
            results.append(result)

        # Проверяем все результаты
        collected = collect_results(results)

        match collected:
            case Success(users):
                # Все успешно - коммитим
                await uow.commit()
                return Success(users)

            case Failure(error):
                # Любая ошибка - rollback всего
                return Failure(error)
```

**Преимущества**:
- ✅ Одна транзакция (быстро)
- ✅ All-or-nothing (атомарность)
- ✅ Автоматический rollback

---

## Пример 5: Custom query в репозитории

### Добавление нового метода в репозиторий

```python
# backend/repositories/recruiter.py

from sqlalchemy import select, func
from backend.core.result import Result, DatabaseError, success, failure

class RecruiterRepository(BaseRepository[Recruiter]):
    # ... базовые методы наследуются

    async def get_with_slot_count(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Result[list[tuple[Recruiter, int]], DatabaseError]:
        """
        Get recruiters with their slot count in date range.

        Returns:
            List of (Recruiter, slot_count) tuples
        """
        try:
            stmt = (
                select(
                    Recruiter,
                    func.count(Slot.id).label("slot_count")
                )
                .outerjoin(Slot)
                .where(
                    Recruiter.active.is_(True),
                    Slot.start_utc.between(start_date, end_date)
                )
                .group_by(Recruiter.id)
                .order_by(Recruiter.name.asc())
            )

            result = await self.session.execute(stmt)
            data = result.all()

            return success(data)

        except Exception as e:
            return failure(DatabaseError(
                operation="RecruiterRepository.get_with_slot_count",
                message=str(e),
                original_exception=e,
            ))
```

### Использование

```python
async with UnitOfWork() as uow:
    result = await uow.recruiters.get_with_slot_count(start_date, end_date)

    match result:
        case Success(data):
            for recruiter, count in data:
                print(f"{recruiter.name}: {count} slots")

        case Failure(error):
            logger.error(f"Error: {error}")
```

---

## Миграционный чеклист

### Шаг 1: Определите границы
- [ ] Выберите модуль для миграции (например, recruiters)
- [ ] Определите все функции, использующие эту модель
- [ ] Проверьте тесты

### Шаг 2: Создайте/используйте репозиторий
- [ ] Убедитесь, что репозиторий существует (например, `RecruiterRepository`)
- [ ] Добавьте специфичные методы, если нужны

### Шаг 3: Замените функции
- [ ] Замените `async_session()` на `UnitOfWork()`
- [ ] Замените прямые вызовы БД на репозиторий
- [ ] Добавьте обработку Result типов

### Шаг 4: Обновите обработку ошибок
- [ ] Замените try/except на match/case
- [ ] Используйте явные типы ошибок
- [ ] Добавьте логирование через logger

### Шаг 5: Обновите тесты
- [ ] Мокайте репозитории вместо БД
- [ ] Тестируйте Success и Failure кейсы
- [ ] Проверьте транзакционность

### Шаг 6: Code review и рефакторинг
- [ ] Проверьте типы (mypy)
- [ ] Убедитесь в покрытии тестами
- [ ] Оптимизируйте запросы

---

## Полезные паттерны

### 1. Early return при ошибке

```python
async with UnitOfWork() as uow:
    result = await uow.users.get(user_id)

    if result.is_failure():
        return result  # Пробрасываем ошибку дальше

    user = result.unwrap()
    # Продолжаем работу...
```

### 2. Transform value

```python
result = await uow.users.get(user_id)

# Извлекаем email из user
email_result = result.map(lambda user: user.email)
```

### 3. Chain operations

```python
result = (
    await uow.users.get(user_id)
    .flat_map(lambda user: uow.orders.get_for_user(user.id))
    .map(lambda orders: len(orders))
)
```

### 4. Collect multiple results

```python
results = [
    await uow.users.get(1),
    await uow.users.get(2),
    await uow.users.get(3),
]

# Success([user1, user2, user3]) или первый Failure
all_users = collect_results(results)
```

---

## FAQ

**Q: Нужно ли мигрировать весь код сразу?**
A: Нет! Мигрируйте постепенно, модуль за модулем. Старый и новый код могут сосуществовать.

**Q: Как тестировать новый код?**
A: Мокайте репозитории:
```python
class MockUserRepository:
    async def get(self, id):
        return Success(User(id=id, name="Test"))
```

**Q: Что делать с существующими тестами?**
A: Обновляйте постепенно. Старые тесты продолжат работать.

**Q: Производительность?**
A: UnitOfWork добавляет минимальный overhead. Batch операции стали быстрее (одна транзакция).

**Q: Как отладить Result типы?**
A: Используйте `result.unwrap()` для получения значения или ошибки.
