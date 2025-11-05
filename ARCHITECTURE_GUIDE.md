# Backend Architecture Guide

## Обзор новой архитектуры

Система переведена на современный паттерн с использованием:
- **Repository Pattern** - инкапсуляция доступа к данным
- **Unit of Work** - управление транзакциями
- **Result Pattern** - типобезопасная обработка ошибок

## Структура

```
backend/
├── core/
│   ├── repository/         # Базовые классы репозиториев
│   │   ├── __init__.py
│   │   ├── base.py         # BaseRepository
│   │   └── protocols.py    # Интерфейсы
│   ├── result.py           # Result/Success/Failure типы
│   ├── uow.py              # Unit of Work
│   └── db.py               # Database setup
├── repositories/           # Конкретные репозитории
│   ├── recruiter.py
│   ├── city.py
│   ├── slot.py
│   ├── template.py
│   └── user.py
├── domain/                 # Модели данных
└── apps/                   # Приложения (API, UI, Bot)
```

## Использование

### 1. Простой запрос через Repository

```python
from backend.core.uow import UnitOfWork

async def get_active_recruiters():
    async with UnitOfWork() as uow:
        result = await uow.recruiters.get_active()

        match result:
            case Success(recruiters):
                return recruiters
            case Failure(error):
                logger.error(f"Failed to get recruiters: {error}")
                return []
```

### 2. Операции с транзакциями

```python
from backend.core.uow import UnitOfWork
from backend.domain.models import Recruiter

async def create_recruiter(name: str, tg_chat_id: int):
    async with UnitOfWork() as uow:
        # Создаем рекрутера
        recruiter = Recruiter(name=name, tg_chat_id=tg_chat_id)
        result = await uow.recruiters.add(recruiter)

        if result.is_failure():
            # Ошибка, транзакция не будет закоммичена
            return result

        # Коммитим транзакцию
        await uow.commit()

        return result
```

### 3. Сложные операции с несколькими репозиториями

```python
from backend.core.uow import UnitOfWork
from backend.domain.models import Slot, SlotStatus

async def book_slot(slot_id: int, candidate_telegram_id: int):
    async with UnitOfWork() as uow:
        # Получаем слот
        slot_result = await uow.slots.get(slot_id)
        if slot_result.is_failure():
            return slot_result

        slot = slot_result.unwrap()

        # Проверяем, что слот свободен
        if slot.status != SlotStatus.FREE:
            return failure(ValidationError(
                field="status",
                message="Slot is not available"
            ))

        # Обновляем слот
        slot.status = SlotStatus.RESERVED
        slot.telegram_id = candidate_telegram_id

        update_result = await uow.slots.update(slot)
        if update_result.is_failure():
            return update_result

        # Создаем уведомление
        # ... (через соответствующий репозиторий)

        # Коммитим все изменения атомарно
        await uow.commit()

        return update_result
```

### 4. Работа с Result Pattern

```python
from backend.core.result import Success, Failure, collect_results

# Получение значения
result = await uow.users.get(user_id)

# Pattern matching (Python 3.10+)
match result:
    case Success(user):
        print(f"Found user: {user.name}")
    case Failure(NotFoundError() as error):
        print(f"User not found: {error}")
    case Failure(error):
        print(f"Database error: {error}")

# Unwrap (raises if Failure)
user = result.unwrap()

# Unwrap with default
user = result.unwrap_or(default_user)

# Transform value
result = await uow.users.get(user_id)
email_result = result.map(lambda user: user.email)

# Chain operations
result = await uow.users.get(user_id)
order_result = result.flat_map(lambda user: uow.orders.get_for_user(user.id))

# Collect multiple results
results = [
    await uow.users.get(1),
    await uow.users.get(2),
    await uow.users.get(3),
]
all_users = collect_results(results)  # Success([user1, user2, user3]) or Failure
```

### 5. Создание custom репозитория

```python
from backend.core.repository.base import BaseRepository
from backend.core.result import DatabaseError, Result, failure, success
from backend.domain.models import Recruiter
from sqlalchemy import select

class RecruiterRepository(BaseRepository[Recruiter]):
    """Repository for Recruiter entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(Recruiter, session)

    # Наследуем все базовые методы:
    # - get(id)
    # - get_all(limit, offset)
    # - add(entity)
    # - update(entity)
    # - delete(id)
    # - exists(id)
    # - count()

    # Добавляем специфичные методы
    async def get_active(self) -> Result[Sequence[Recruiter], DatabaseError]:
        try:
            stmt = (
                select(Recruiter)
                .where(Recruiter.active.is_(True))
                .order_by(Recruiter.name.asc())
            )
            result = await self.session.execute(stmt)
            recruiters = result.scalars().all()

            return success(recruiters)

        except Exception as e:
            return failure(DatabaseError(
                operation="Recruiter.get_active",
                message=str(e),
                original_exception=e,
            ))
```

## Преимущества новой архитектуры

### 1. Типобезопасность
```python
# Старый подход
user = await get_user(user_id)  # Optional[User] или raises
if user is None:
    # обработка ошибки

# Новый подход
result = await uow.users.get(user_id)  # Result[User, Error]
match result:
    case Success(user):
        # user: User - гарантированно существует
    case Failure(error):
        # error: NotFoundError | DatabaseError - явная обработка
```

### 2. Testability
```python
# Mock репозитория легко
class MockUserRepository:
    async def get(self, id: int):
        return Success(User(id=id, name="Test"))

# Инжектим в UnitOfWork для тестов
uow = UnitOfWork(mock_session)
uow.users = MockUserRepository()
```

### 3. Транзакции
```python
# Все операции в одной транзакции
async with UnitOfWork() as uow:
    await uow.users.add(user)
    await uow.orders.add(order)
    await uow.commit()  # Атомарно
```

### 4. Чистый код
```python
# Разделение concerns
# Service Layer - бизнес-логика
# Repository Layer - доступ к данным
# Domain Layer - модели
```

## Migration Guide

### Из старого кода в новый

**Было:**
```python
from backend.domain.repositories import get_active_recruiters

recruiters = await get_active_recruiters()
```

**Стало:**
```python
from backend.core.uow import UnitOfWork

async with UnitOfWork() as uow:
    result = await uow.recruiters.get_active()
    recruiters = result.unwrap_or([])
```

**Было (с ошибками):**
```python
try:
    recruiter = await get_recruiter(id)
    if recruiter is None:
        raise ValueError("Not found")
    # ...
except Exception as e:
    logger.error(f"Error: {e}")
    return None
```

**Стало:**
```python
async with UnitOfWork() as uow:
    result = await uow.recruiters.get(id)

    match result:
        case Success(recruiter):
            # работаем с recruiter
            pass
        case Failure(NotFoundError()):
            # явная обработка "не найдено"
            pass
        case Failure(DatabaseError() as e):
            # явная обработка ошибки БД
            logger.error(f"DB Error: {e}")
```

## Best Practices

### 1. Всегда используйте UnitOfWork
```python
# ✅ Good
async with UnitOfWork() as uow:
    result = await uow.users.get(id)
    await uow.commit()

# ❌ Bad
from backend.core.db import async_session
async with async_session() as session:
    # Прямое использование session
```

### 2. Обрабатывайте ошибки явно
```python
# ✅ Good
result = await uow.users.get(id)
if result.is_failure():
    return handle_error(result.error)

user = result.unwrap()

# ❌ Bad
user = await uow.users.get(id).unwrap()  # Может упасть
```

### 3. Коммитьте транзакции явно
```python
# ✅ Good
async with UnitOfWork() as uow:
    await uow.users.add(user)
    await uow.commit()  # Явный commit

# ❌ Bad (нет commit)
async with UnitOfWork() as uow:
    await uow.users.add(user)
    # Изменения потеряются
```

### 4. Используйте flush для получения ID
```python
async with UnitOfWork() as uow:
    await uow.users.add(user)
    await uow.flush()  # Получаем user.id без commit

    order = Order(user_id=user.id)
    await uow.orders.add(order)

    await uow.commit()
```

## Performance Tips

### 1. Batch operations
```python
# ✅ Good - одна транзакция
async with UnitOfWork() as uow:
    for user in users:
        await uow.users.add(user)
    await uow.commit()

# ❌ Bad - N транзакций
for user in users:
    async with UnitOfWork() as uow:
        await uow.users.add(user)
        await uow.commit()
```

### 2. Eager loading
```python
class SlotRepository(BaseRepository[Slot]):
    async def get_with_relations(self, id: int):
        stmt = (
            select(Slot)
            .where(Slot.id == id)
            .options(
                selectinload(Slot.recruiter),
                selectinload(Slot.city),
            )
        )
        # Загружает связи в одном запросе
```

### 3. Query result reuse
```python
async with UnitOfWork() as uow:
    result = await uow.users.get_active()
    active_users = result.unwrap_or([])

    # Переиспользуем session для связанных запросов
    for user in active_users:
        orders = await uow.orders.get_for_user(user.id)
```

## Next Steps

1. ✅ Phase 1 завершена - Repository, UnitOfWork, Result
2. 🔄 Phase 2 - Кэширование (Redis)
3. ⏳ Phase 3 - Метрики и мониторинг
4. ⏳ Phase 4 - CQRS и Event Sourcing
