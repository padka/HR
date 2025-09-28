from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import delete, func, select, case, update, or_
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from backend.core.db import async_session
from backend.domain.models import City, Recruiter, Slot, SlotStatus, Template, TestQuestion
from backend.domain.template_stages import CITY_TEMPLATE_STAGES, STAGE_DEFAULTS

# -----------------------------
# ВСПОМОГАТЕЛЬНЫЕ КОНСТАНТЫ/ФУНКЦИИ
# -----------------------------

from backend.apps.admin_ui.utils import (
    fmt_local,
    norm_status,
    paginate,
    recruiter_time_to_utc,
    status_to_db,
)

# -----------------------------
# DASHBOARD / СЧЁТЧИКИ
# -----------------------------

TEST_LABELS = {
    "test1": "Анкета кандидата",
    "test2": "Инфо-тест",
}

STAGE_KEYS: List[str] = [stage.key for stage in CITY_TEMPLATE_STAGES]

async def dashboard_counts() -> Dict[str, int]:
    async with async_session() as session:
        rec_count = await session.scalar(select(func.count()).select_from(Recruiter))
        city_count = await session.scalar(select(func.count()).select_from(City))
        rows = (await session.execute(select(Slot.status, func.count()).group_by(Slot.status))).all()

    status_map: Dict[str, int] = {
        (status.value if hasattr(status, "value") else status): count for status, count in rows
    }
    total = sum(status_map.values())

    def _norm(name: str) -> str:
        obj = getattr(SlotStatus, name, name)
        return obj.value if hasattr(obj, "value") else obj

    return {
        "recruiters": rec_count or 0,
        "cities": city_count or 0,
        "slots_total": total,
        "slots_free": status_map.get(_norm("FREE"), 0),
        "slots_pending": status_map.get(_norm("PENDING"), 0),
        "slots_booked": status_map.get(_norm("BOOKED"), 0),
    }


# -----------------------------
# РЕКРУТЕРЫ / ГОРОДА / СЛОТЫ
# -----------------------------

async def list_recruiters(order_by_name: bool = True) -> List[Recruiter]:
    async with async_session() as session:
        query = select(Recruiter)
        if order_by_name:
            query = query.order_by(Recruiter.name.asc())
        recs = list((await session.scalars(query)).all())

        stats_map: Dict[int, Dict[str, object]] = {}
        city_map: Dict[int, List[Tuple[str, str]]] = {}

        if recs:
            rec_ids = [r.id for r in recs]
            stats_rows = (await session.execute(
                select(
                    Slot.recruiter_id,
                    func.count().label("total"),
                    func.sum(case((Slot.status == SlotStatus.FREE, 1), else_=0)).label("free"),
                    func.sum(case((Slot.status == SlotStatus.PENDING, 1), else_=0)).label("pending"),
                    func.sum(case((Slot.status == SlotStatus.BOOKED, 1), else_=0)).label("booked"),
                    func.min(case((Slot.status == SlotStatus.FREE, Slot.start_utc), else_=None)).label("next_free"),
                ).where(Slot.recruiter_id.in_(rec_ids)).group_by(Slot.recruiter_id)
            )).all()

            stats_map = {
                row.recruiter_id: {
                    "total": int(row.total or 0),
                    "free": int(row.free or 0),
                    "pending": int(row.pending or 0),
                    "booked": int(row.booked or 0),
                    "next_free": row.next_free,
                }
                for row in stats_rows
            }

            city_rows = (await session.execute(
                select(City.id, City.name, City.tz, City.responsible_recruiter_id)
                .where(City.responsible_recruiter_id.in_(rec_ids))
                .order_by(City.name.asc())
            )).all()

            for row in city_rows:
                city_map.setdefault(row.responsible_recruiter_id, []).append((row.name, row.tz))

    now = datetime.now(timezone.utc)
    out = []
    for rec in recs:
        stats = stats_map.get(rec.id, {"total": 0, "free": 0, "pending": 0, "booked": 0, "next_free": None})
        next_dt = stats.get("next_free")
        if next_dt is not None and next_dt.tzinfo is None:
            next_dt = next_dt.replace(tzinfo=timezone.utc)
        if isinstance(next_dt, datetime) and next_dt.tzinfo is not None:
            stats["next_free"] = next_dt
            next_local = fmt_local(next_dt, getattr(rec, "tz", None) or "Europe/Moscow")
            next_future = next_dt > now
        else:
            next_local = None
            next_future = False
        out.append(
            {
                "rec": rec,
                "stats": stats,
                "next_free_local": next_local,
                "next_is_future": next_future,
                "cities": city_map.get(rec.id, []),
                "cities_text": " ".join(name.lower() for name, _ in city_map.get(rec.id, [])),
            }
        )

    return out


async def list_cities(order_by_name: bool = True) -> List[City]:
    async with async_session() as session:
        query = select(City)
        if order_by_name:
            query = query.order_by(City.name.asc())
        return (await session.scalars(query)).all()


# -----------------------------
# ШАБЛОНЫ СТАДИЙ / ГОРОДА
# -----------------------------

async def get_stage_templates(
    *, city_ids: Optional[Sequence[int]] = None, include_global: bool = False
) -> Dict[Optional[int], Dict[str, str]]:
    conditions = [Template.key.in_(STAGE_KEYS)]
    filters = []
    if city_ids:
        filters.append(Template.city_id.in_(city_ids))
    if include_global:
        filters.append(Template.city_id.is_(None))

    if filters:
        query = select(Template).where(or_(*filters), *conditions)
    else:
        query = select(Template).where(*conditions)

    async with async_session() as session:
        items = (await session.scalars(query)).all()

    data: Dict[Optional[int], Dict[str, str]] = {}
    for item in items:
        data.setdefault(item.city_id, {})[item.key] = item.content

    if city_ids:
        for cid in city_ids:
            data.setdefault(cid, {})
    if include_global:
        data.setdefault(None, {})
    return data


def stage_payload_for_ui(stored: Dict[str, str]) -> List[Dict[str, object]]:
    result: List[Dict[str, object]] = []
    for stage in CITY_TEMPLATE_STAGES:
        value = stored.get(stage.key, "")
        result.append(
            {
                "key": stage.key,
                "title": stage.title,
                "description": stage.description,
                "value": value,
                "default": STAGE_DEFAULTS.get(stage.key, ""),
                "is_custom": bool(value.strip()),
            }
        )
    return result


async def templates_overview() -> Dict[str, object]:
    cities = await list_cities()
    city_ids = [c.id for c in cities]
    raw_map = await get_stage_templates(city_ids=city_ids, include_global=True)

    city_payload = [
        {
            "city": city,
            "stages": stage_payload_for_ui(raw_map.get(city.id, {})),
        }
        for city in cities
    ]

    global_payload = stage_payload_for_ui(raw_map.get(None, {}))

    return {
        "cities": city_payload,
        "global": {
            "stages": global_payload,
        },
        "stage_meta": CITY_TEMPLATE_STAGES,
    }


async def update_templates_for_city(
    city_id: Optional[int], templates: Dict[str, Optional[str]]
) -> None:
    valid_keys = set(STAGE_KEYS)
    cleaned = {key: (templates.get(key) or "").strip() for key in valid_keys}

    async with async_session() as session:
        if city_id is None:
            query = select(Template).where(Template.key.in_(valid_keys), Template.city_id.is_(None))
        else:
            query = select(Template).where(Template.key.in_(valid_keys), Template.city_id == city_id)
        existing = {item.key: item for item in (await session.scalars(query)).all()}

        for key in valid_keys:
            text_value = cleaned.get(key, "")
            tmpl = existing.get(key)
            if text_value:
                if tmpl:
                    tmpl.content = text_value
                else:
                    session.add(Template(city_id=city_id, key=key, content=text_value))
            elif tmpl:
                await session.delete(tmpl)

        await session.commit()


async def update_city_settings(
    city_id: int,
    *,
    responsible_id: Optional[int],
    templates: Dict[str, Optional[str]],
) -> Optional[str]:
    owner_field = city_owner_field_name()
    async with async_session() as session:
        city = await session.get(City, city_id)
        if not city:
            return "City not found"

        if responsible_id is not None:
            recruiter = await session.get(Recruiter, responsible_id)
            if not recruiter:
                return "Recruiter not found"

        if owner_field:
            setattr(city, owner_field, responsible_id)
        await session.commit()

    await update_templates_for_city(city_id, templates)
    return None


# -----------------------------
# СЛОТЫ / ФОРМЫ / ЛИСТИНГ
# -----------------------------

async def list_slots(
    recruiter_id: Optional[int],
    status: Optional[str],
    page: int,
    per_page: int,
):
    async with async_session() as session:
        base = select(Slot)
        if recruiter_id is not None:
            base = base.where(Slot.recruiter_id == recruiter_id)
        if status:
            base = base.where(Slot.status == status_to_db(status))

        total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
        pages_total, page, offset = paginate(total, page, per_page)

        query = (
            base.options(selectinload(Slot.recruiter))
            .order_by(Slot.start_utc.desc())
            .offset(offset)
            .limit(per_page)
        )
        items = (await session.scalars(query)).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "pages_total": pages_total,
    }


def city_owner_field_name() -> Optional[str]:
    inspector = sa_inspect(City)
    attrs = set(inspector.attrs.keys())
    cols = set(getattr(inspector, "columns", {}).keys()) if hasattr(inspector, "columns") else set()
    allowed = attrs | cols
    for name in ["responsible_recruiter_id", "owner_id", "recruiter_id", "manager_id"]:
        if name in allowed:
            return name
    return None


async def recruiters_for_slot_form() -> List[Recruiter]:
    inspector = sa_inspect(Recruiter)
    has_active = "active" in getattr(inspector, "columns", {})
    query = select(Recruiter).order_by(Recruiter.name.asc())
    if has_active:
        query = query.where(getattr(Recruiter, "active") == True)  # noqa: E712
    async with async_session() as session:
        return (await session.scalars(query)).all()


async def create_slot(recruiter_id: int, date: str, time: str) -> bool:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, recruiter_id)
        if not recruiter:
            return False
        dt_utc = recruiter_time_to_utc(date, time, getattr(recruiter, "tz", None))
        if not dt_utc:
            return False
        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value
        session.add(Slot(recruiter_id=recruiter_id, start_utc=dt_utc, status=status_free))
        await session.commit()
        return True


# -----------------------------
# РЕКРУТЕРЫ CRUD
# -----------------------------

async def create_recruiter(payload: Dict[str, object], *, cities: Optional[List[str]] = None) -> None:
    async with async_session() as session:
        recruiter = Recruiter(**payload)
        session.add(recruiter)
        await session.commit()
        await session.refresh(recruiter)

        selected: List[int] = []
        if cities:
            for cid in cities:
                if cid and cid.strip().isdigit():
                    selected.append(int(cid.strip()))
        if selected:
            await session.execute(
                update(City)
                .where(City.id.in_(selected))
                .values(responsible_recruiter_id=recruiter.id)
            )
            await session.commit()


async def get_recruiter_detail(rec_id: int) -> Optional[Dict[str, object]]:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, rec_id)
        if not recruiter:
            return None
        cities = (await session.scalars(select(City).order_by(City.name.asc()))).all()
        selected_ids = {c.id for c in cities if c.responsible_recruiter_id == rec_id}
    return {
        "recruiter": recruiter,
        "cities": cities,
        "selected_ids": selected_ids,
    }


async def update_recruiter(rec_id: int, payload: Dict[str, object], *, cities: Optional[List[str]] = None) -> bool:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, rec_id)
        if not recruiter:
            return False

        for key, value in payload.items():
            setattr(recruiter, key, value)

        selected: List[int] = []
        if cities:
            for cid in cities:
                if cid and cid.strip().isdigit():
                    selected.append(int(cid.strip()))

        # Снимаем текущие привязки города к этому рекрутеру
        await session.execute(
            update(City)
            .where(City.responsible_recruiter_id == rec_id)
            .values(responsible_recruiter_id=None)
        )
        # Назначаем новые, если есть
        if selected:
            await session.execute(
                update(City)
                .where(City.id.in_(selected))
                .values(responsible_recruiter_id=rec_id)
            )

        # ВАЖНО: коммит ДОЛЖЕН БЫТЬ внутри контекста сессии
        await session.commit()

    return True


async def delete_recruiter(rec_id: int) -> None:
    async with async_session() as session:
        recruiter = await session.get(Recruiter, rec_id)
        if not recruiter:
            return
        await session.execute(
            update(City)
            .where(City.responsible_recruiter_id == rec_id)
            .values(responsible_recruiter_id=None)
        )
        await session.delete(recruiter)
        await session.commit()


def build_recruiter_payload(
    *,
    name: str,
    tz: str,
    telemost: Optional[str],
    tg_chat_id: Optional[str],
    active: Optional[str],
) -> Dict[str, object]:
    allowed = set(sa_inspect(Recruiter).attrs.keys())
    payload: Dict[str, object] = {"name": name.strip()}

    tz_field = _pick_field(allowed, ["tz", "timezone", "tz_name", "time_zone"])
    if tz_field:
        payload[tz_field] = tz.strip() if tz else "Europe/Moscow"

    link = (telemost or "").strip() or None
    telemost_field = _pick_field(
        allowed,
        ["telemost_url", "telemost", "meet_link", "meet_url", "video_link", "video_url", "link", "room_url"],
    )
    if telemost_field:
        payload[telemost_field] = link

    chat_field = _pick_field(allowed, ["tg_chat_id", "telegram_chat_id", "chat_id"])
    if chat_field:
        if tg_chat_id and tg_chat_id.strip().isdigit():
            payload[chat_field] = int(tg_chat_id.strip())
        else:
            payload[chat_field] = None

    active_field = _pick_field(allowed, ["active", "is_active", "enabled"])
    if active_field:
        payload[active_field] = True if active else False

    return payload


def _pick_field(allowed: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    for name in candidates:
        if name in allowed:
            return name
    return None


# -----------------------------
# ГОРОДА CRUD / ВЛАДЕЛЕЦ
# -----------------------------

async def create_city(name: str, tz: str) -> None:
    async with async_session() as session:
        session.add(City(name=name.strip(), tz=tz.strip() if tz else "Europe/Moscow"))
        await session.commit()


async def assign_city_owner(city_id: int, recruiter_id: Optional[int]) -> Optional[str]:
    owner_field = city_owner_field_name()
    if not owner_field:
        return "Owner field is missing on City model."

    async with async_session() as session:
        city = await session.get(City, city_id)
        if not city:
            return "City not found"

        if recruiter_id is not None:
            recruiter = await session.get(Recruiter, recruiter_id)
            if not recruiter:
                return "Recruiter not found"

        setattr(city, owner_field, recruiter_id)
        await session.commit()
    return None


# -----------------------------
# ШАБЛОНЫ CRUD / API-ПОМОЩНИКИ
# -----------------------------

async def list_templates() -> Dict[str, object]:
    overview = await templates_overview()
    return overview


async def create_template(key: str, text: str, city_id: Optional[int]) -> None:
    async with async_session() as session:
        session.add(Template(city_id=city_id, key=key.strip(), content=text))
        await session.commit()


async def get_template(tmpl_id: int) -> Optional[Template]:
    async with async_session() as session:
        return await session.get(Template, tmpl_id)


async def update_template(tmpl_id: int, *, key: str, text: str, city_id: Optional[int]) -> bool:
    async with async_session() as session:
        tmpl = await session.get(Template, tmpl_id)
        if not tmpl:
            return False
        tmpl.city_id = city_id
        tmpl.key = key.strip()
        tmpl.content = text
        await session.commit()
        return True


async def delete_template(tmpl_id: int) -> None:
    async with async_session() as session:
        await session.execute(delete(Template).where(Template.id == tmpl_id))
        await session.commit()


# -----------------------------
# API-ПЕЙЛОАДЫ ДЛЯ UI
# -----------------------------

async def api_recruiters_payload() -> List[Dict[str, object]]:
    async with async_session() as session:
        recs = (await session.scalars(select(Recruiter).order_by(Recruiter.id.asc()))).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "tz": getattr(r, "tz", None),
            "tg_chat_id": getattr(r, "tg_chat_id", None),
            "active": getattr(r, "active", True),
        }
        for r in recs
    ]


async def api_cities_payload() -> List[Dict[str, object]]:
    owner_field = city_owner_field_name()
    async with async_session() as session:
        cities = (await session.scalars(select(City).order_by(City.id.asc()))).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "tz": getattr(c, "tz", None),
            "owner_recruiter_id": getattr(c, owner_field) if owner_field else None,
        }
        for c in cities
    ]


async def api_slots_payload(
    recruiter_id: Optional[int],
    status: Optional[str],
    limit: int,
) -> List[Dict[str, object]]:
    async with async_session() as session:
        query = select(Slot).options(selectinload(Slot.recruiter)).order_by(Slot.start_utc.asc())
        if recruiter_id is not None:
            query = query.where(Slot.recruiter_id == recruiter_id)
        if status:
            query = query.where(Slot.status == status_to_db(status))
        if limit:
            query = query.limit(max(1, min(500, limit)))
        slots = (await session.scalars(query)).all()
    return [
        {
            "id": sl.id,
            "recruiter_id": sl.recruiter_id,
            "recruiter_name": sl.recruiter.name if sl.recruiter else None,
            "start_utc": sl.start_utc.isoformat(),
            "status": norm_status(sl.status),
            "candidate_fio": getattr(sl, "candidate_fio", None),
            "candidate_tg_id": getattr(sl, "candidate_tg_id", None),
        }
        for sl in slots
    ]


async def api_templates_payload(
    city_id: Optional[int],
    key: Optional[str],
) -> Optional[object]:
    async with async_session() as session:
        query = select(Template)
        if city_id is not None and key is not None:
            obj = (await session.scalars(query.where(Template.city_id == city_id, Template.key == key))).first()
            if obj:
                return {
                    "found": True,
                    "id": obj.id,
                    "city_id": obj.city_id,
                    "key": obj.key,
                    "text": obj.content,
                    "is_global": obj.city_id is None,
                }
            fallback = (
                await session.scalars(query.where(Template.city_id.is_(None), Template.key == key))
            ).first()
            if fallback:
                return {
                    "found": True,
                    "id": fallback.id,
                    "city_id": fallback.city_id,
                    "key": fallback.key,
                    "text": fallback.content,
                    "is_global": True,
                }
            return {"found": False}

        if city_id is not None:
            city_items = (
                await session.scalars(query.where(Template.city_id == city_id))
            ).all()
            global_items = (
                await session.scalars(query.where(Template.city_id.is_(None)))
            ).all()
            items = city_items + global_items
        elif key is not None:
            items = (await session.scalars(query.where(Template.key == key))).all()
        else:
            items = (await session.scalars(query)).all()

    return [
        {
            "id": t.id,
            "city_id": t.city_id,
            "key": t.key,
            "text": t.content,
            "is_global": t.city_id is None,
        }
        for t in items
    ]


async def api_city_owners_payload() -> Dict[str, object]:
    owner_field = city_owner_field_name()
    if not owner_field:
        return {"ok": False, "error": "Owner field is missing on City model."}
    async with async_session() as session:
        cities = (await session.scalars(select(City))).all()
    return {
        "ok": True,
        "owners": {c.id: getattr(c, owner_field, None) for c in cities},
    }


# -----------------------------
# ТЕСТОВЫЕ ВОПРОСЫ
# -----------------------------

def _parse_question_payload(payload: str) -> Dict[str, object]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _question_kind(data: Dict[str, object]) -> str:
    options = data.get("options")
    if isinstance(options, list) and options:
        return "choice"
    return "text"


def _correct_option_label(data: Dict[str, object]) -> Optional[str]:
    options = data.get("options")
    correct = data.get("correct")
    if isinstance(options, list) and isinstance(correct, int):
        if 0 <= correct < len(options):
            return str(options[correct])
    return None


async def list_test_questions() -> List[Dict[str, object]]:
    async with async_session() as session:
        items = (
            await session.scalars(
                select(TestQuestion).order_by(TestQuestion.test_id.asc(), TestQuestion.question_index.asc())
            )
        ).all()

    grouped: Dict[str, Dict[str, object]] = {}
    for item in items:
        data = _parse_question_payload(item.payload)
        grouped.setdefault(
            item.test_id,
            {
                "test_id": item.test_id,
                "title": TEST_LABELS.get(item.test_id, item.test_id),
                "questions": [],
            },
        )["questions"].append(
            {
                "id": item.id,
                "index": item.question_index,
                "title": item.title,
                "prompt": data.get("prompt") or data.get("text") or item.title,
                "kind": _question_kind(data),
                "options_count": len(data.get("options") or []),
                "correct_label": _correct_option_label(data),
                "is_active": item.is_active,
                "updated_at": item.updated_at,
            }
        )

    ordered: List[Dict[str, object]] = []
    known_order = list(TEST_LABELS.keys())
    extra_ids = [tid for tid in grouped.keys() if tid not in known_order]
    for test_id in [*known_order, *sorted(extra_ids)]:
        if test_id not in grouped:
            continue
        questions = sorted(grouped[test_id]["questions"], key=lambda q: q["index"])
        grouped[test_id]["questions"] = questions
        ordered.append(grouped[test_id])

    return ordered


async def get_test_question_detail(question_id: int) -> Optional[Dict[str, object]]:
    async with async_session() as session:
        question = await session.get(TestQuestion, question_id)
        if not question:
            return None

    data = _parse_question_payload(question.payload)
    pretty = json.dumps(data or {}, ensure_ascii=False, indent=2, sort_keys=True)
    return {
        "question": question,
        "payload_json": pretty,
        "test_choices": list(TEST_LABELS.items()),
    }


async def update_test_question(
    question_id: int,
    *,
    title: str,
    test_id: str,
    question_index: int,
    payload: str,
    is_active: bool,
) -> Tuple[bool, Optional[str]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return False, "invalid_json"

    if not isinstance(data, dict):
        return False, "invalid_json"

    normalized_payload = json.dumps(data, ensure_ascii=False)
    resolved_title = title.strip() or data.get("prompt") or data.get("text")
    if not resolved_title:
        resolved_title = f"Вопрос {question_index}"

    clean_test_id = test_id.strip()
    if not clean_test_id:
        return False, "test_required"

    async with async_session() as session:
        question = await session.get(TestQuestion, question_id)
        if not question:
            return False, "not_found"

        question.title = resolved_title
        question.test_id = clean_test_id
        question.question_index = question_index
        question.payload = normalized_payload
        question.is_active = is_active
        question.updated_at = datetime.now(timezone.utc)

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False, "duplicate_index"

    return True, None