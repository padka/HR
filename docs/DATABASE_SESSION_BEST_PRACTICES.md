# Database Session Best Practices

## Проблема: Утечка подключений к PostgreSQL

При неправильном использовании SQLAlchemy AsyncSession могут возникать утечки подключений к базе данных, что приводит к:
- Предупреждениям "garbage collector is trying to clean up non-checked-in connection"
- Истощению пула подключений (pool exhausted)
- Деградации производительности приложения

## Правильные паттерны использования AsyncSession

### 1. Всегда используйте контекстный менеджер

✅ **ПРАВИЛЬНО:**
```python
async def get_user(user_id: int) -> Optional[User]:
    async with async_session() as session:
        user = await session.get(User, user_id)
        if user:
            session.expunge(user)  # Отсоединяем от сессии
        return user
```

❌ **НЕПРАВИЛЬНО:**
```python
async def get_user(user_id: int) -> Optional[User]:
    session = new_async_session()  # Сессия может не закрыться!
    user = await session.get(User, user_id)
    return user  # УТЕЧКА!
```

### 2. Отсоединяйте ORM объекты перед возвратом (expunge)

Если функция возвращает ORM объекты, которые будут использоваться после закрытия сессии:

✅ **ПРАВИЛЬНО:**
```python
async def list_messages(user_id: int) -> List[Message]:
    async with async_session() as session:
        result = await session.execute(
            select(Message).where(Message.user_id == user_id)
        )
        messages = list(result.scalars())
        # Отсоединяем все объекты от сессии
        for msg in messages:
            session.expunge(msg)
        return messages
```

❌ **НЕПРАВИЛЬНО:**
```python
async def list_messages(user_id: int) -> List[Message]:
    async with async_session() as session:
        result = await session.execute(
            select(Message).where(Message.user_id == user_id)
        )
        return list(result.scalars())  # Объекты привязаны к сессии!
```

### 3. Eager loading для связанных данных

Загружайте все необходимые связи ДО закрытия сессии:

✅ **ПРАВИЛЬНО:**
```python
from sqlalchemy.orm import selectinload

async def get_slot_with_relations(slot_id: int) -> Optional[Slot]:
    async with async_session() as session:
        result = await session.execute(
            select(Slot)
            .options(
                selectinload(Slot.recruiter),
                selectinload(Slot.city)
            )
            .where(Slot.id == slot_id)
        )
        slot = result.scalar_one_or_none()
        if slot:
            session.expunge(slot)
        return slot
```

### 4. Фоновые задачи должны создавать собственные сессии

❌ **НЕПРАВИЛЬНО - передача сессии в background task:**
```python
@router.post("/items")
async def create_item(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session)
):
    # НЕ передавайте session в background task!
    background_tasks.add_task(process_item, item, session)
```

✅ **ПРАВИЛЬНО - создание новой сессии внутри задачи:**
```python
async def process_item_background(item_id: int):
    # Создаем НОВУЮ сессию внутри фоновой задачи
    async with async_session() as session:
        item = await session.get(Item, item_id)
        # Обработка...
        await session.commit()

@router.post("/items")
async def create_item(background_tasks: BackgroundTasks):
    # Передаем только примитивы (IDs), а не ORM объекты или сессию
    background_tasks.add_task(process_item_background, item.id)
```

### 5. FastAPI Dependency Injection

Используйте DI правильно:

```python
async def get_async_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency для предоставления сессии на запрос."""
    session = new_async_session()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()  # Гарантированное закрытие
```

## Настройки пула подключений

В `backend/core/db.py` настроены параметры пула:

```python
pool_size = 5  # Базовый размер пула
max_overflow = 10  # Дополнительные подключения
pool_timeout = 30  # Таймаут ожидания подключения
pool_pre_ping = True  # Проверка подключения перед использованием
pool_recycle = 3600  # Переиспользование подключений (1 час)
expire_on_commit = False  # Объекты не expired после commit
echo_pool = True  # Логирование пула (только в dev)
```

## Диагностика проблем

### Логи пула (development mode)

При `ENVIRONMENT=development` включено логирование пула (`echo_pool=True`), которое покажет:
- Checkout подключения из пула
- Checkin подключения обратно в пул
- Создание новых подключений

### Проверка состояния пула

Добавьте эндпоинт для мониторинга:

```python
@router.get("/debug/pool-status")
async def pool_status():
    pool = async_engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
    }
```

## Чеклист при добавлении нового кода

- [ ] Все `AsyncSession` создаются через `async with async_session()`
- [ ] Нет прямых вызовов `new_async_session()` без контекстного менеджера
- [ ] ORM объекты, возвращаемые из функций, отсоединены через `session.expunge()`
- [ ] Используется eager loading (`selectinload`, `joinedload`) для связей
- [ ] Фоновые задачи создают собственные сессии
- [ ] Нет передачи `session` или ORM объектов в background tasks
- [ ] FastAPI dependencies правильно закрывают сессии в `finally`

## Исправленные файлы (2025-12-24)

1. `backend/domain/candidates/services.py`:
   - `list_chat_messages()` - добавлен expunge для messages
   - `get_user_by_telegram_id()` - добавлен expunge для user
   - `get_user_by_candidate_id()` - добавлен expunge для user
   - `get_all_active_users()` - добавлен expunge для users

2. `backend/apps/admin_ui/services/slots.py`:
   - `list_slots()` - добавлен expunge для items в цикле

3. `backend/core/db.py`:
   - Добавлен `echo_pool=True` для development окружения

## Дополнительные ресурсы

- [SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Asyncio Extension](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Connection Pool Configuration](https://docs.sqlalchemy.org/en/20/core/pooling.html)
