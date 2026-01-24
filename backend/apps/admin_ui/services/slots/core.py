"""Compatibility bridge to the legacy slots module.

Исторически логика слотов находилась в файле `services/slots.py`.
Одноимённая пакетная директория перекрывает его при импорте, что
приводило к ошибкам импорта в тестах/приложении. Этот модуль
динамически подгружает исходный файл и реэкспортирует его символы.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Dict
import sys

_BASE_DIR = Path(__file__).resolve().parent


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Не удалось загрузить модуль {name} из {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


_legacy_module = _load_module(_BASE_DIR.parent / "slots.py", "backend.apps.admin_ui.services._slots_legacy")
_bulk_module = _load_module(_BASE_DIR / "bulk.py", "backend.apps.admin_ui.services._slots_bulk")
_crud_module = _load_module(_BASE_DIR / "crud.py", "backend.apps.admin_ui.services._slots_crud")
_bot_module = _load_module(_BASE_DIR / "bot.py", "backend.apps.admin_ui.services._slots_bot")


def _collect_exports(module: ModuleType) -> Dict[str, object]:
    return {name: getattr(module, name) for name in dir(module) if not name.startswith("_")}


# Реэкспортируем атрибуты из всех подпакетов и легаси-файла
for _module in (_legacy_module, _bulk_module, _crud_module, _bot_module):
    globals().update(_collect_exports(_module))

# Добавляем служебные функции, начинающиеся с подчёркивания, которые используют другие модули
for name in ("_trigger_test2", "_trigger_rejection", "reject_slot_booking", "reschedule_slot_booking"):
    if hasattr(_legacy_module, name):
        globals()[name] = getattr(_legacy_module, name)

# Дополнительные вспомогательные bulk-операции, которых нет в легаси-файле
from sqlalchemy import select  # type: ignore
from backend.core.db import async_session  # type: ignore
from backend.domain.models import Slot, SlotStatus  # type: ignore


async def bulk_assign_slots(slot_ids, recruiter_id, principal=None):
    principal_id = getattr(principal, "id", None)
    principal_type = getattr(principal, "type", None)
    updated = 0
    async with async_session() as session:
        slots = list(await session.scalars(select(Slot).where(Slot.id.in_(slot_ids))))
        found_ids = {slot.id for slot in slots}
        missing = [sid for sid in slot_ids if sid not in found_ids]
        for slot in slots:
            if principal_type == "recruiter" and slot.recruiter_id != principal_id:
                missing.append(slot.id)
                continue
            slot.recruiter_id = recruiter_id
            updated += 1
        await session.commit()
        return updated, missing


async def bulk_schedule_reminders(slot_ids, principal=None):
    scheduled = 0
    missing = []
    principal_id = getattr(principal, "id", None)
    principal_type = getattr(principal, "type", None)
    getter = globals().get("get_reminder_service")
    if getter is None:
        getter = getattr(_bot_module, "get_reminder_service", None)

    reminder_service = None
    if callable(getter):
        try:
            reminder_service = getter()
        except Exception:
            reminder_service = None
    async with async_session() as session:
        slots = list(await session.scalars(select(Slot).where(Slot.id.in_(slot_ids))))
        found_ids = {slot.id for slot in slots}
        missing = [sid for sid in slot_ids if sid not in found_ids]
        for slot in slots:
            if principal_type == "recruiter" and slot.recruiter_id != principal_id:
                missing.append(slot.id)
                continue
            if reminder_service and slot.candidate_tg_id:
                await reminder_service.schedule_for_slot(slot.id)
                scheduled += 1
    return scheduled, missing


async def bulk_delete_slots(slot_ids, force: bool = False, principal=None):
    deleted = 0
    failed = []
    principal_id = getattr(principal, "id", None)
    principal_type = getattr(principal, "type", None)
    async with async_session() as session:
        slots = list(await session.scalars(select(Slot).where(Slot.id.in_(slot_ids))))
        found_ids = {slot.id for slot in slots}
        failed.extend([sid for sid in slot_ids if sid not in found_ids])
        for slot in slots:
            if principal_type == "recruiter" and slot.recruiter_id != principal_id:
                failed.append(slot.id)
                continue
            if not force and slot.status != SlotStatus.FREE:
                failed.append(slot.id)
                continue
            await session.delete(slot)
            deleted += 1
        if deleted:
            await session.commit()
    return deleted, failed

# Созданию и выдаче слотов используем легаси-реализацию (с валидацией времени/оверлапов).
for _name in ("create_slot", "list_slots", "bulk_create_slots"):
    if hasattr(_legacy_module, _name):
        globals()[_name] = getattr(_legacy_module, _name)

# Собираем __all__ для корректной работы from ... import *
__all__ = [name for name in globals() if not name.startswith("_")]

# Поддерживаем совместимость для точечных импортов в коде/тестах
CORE_MODULE: ModuleType = _legacy_module
__legacy__: Dict[str, object] = {"module": _legacy_module, "path": str(_BASE_DIR.parent / "slots.py")}
