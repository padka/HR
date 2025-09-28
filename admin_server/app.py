# admin_server/app.py
from pathlib import Path
from typing import Dict, Optional, List, Tuple

import json

import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import select, func, delete, update, case
from sqlalchemy.orm import selectinload
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

# используем admin_app.* где лежат db/models
from admin_app.db import init_db, SessionLocal
from admin_app.models import Recruiter, City, Slot, SlotStatus, Template
from backend.domain.models import TestQuestion

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="TG Bot Admin")

# статика и шаблоны
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ---------- диагностика роутов ----------
import logging
from fastapi.routing import APIRoute


@app.on_event("startup")
async def _startup():
    # гарантируем, что таблицы созданы
    await init_db()
    # make useful helpers available in all Jinja templates
    templates.env.globals.update(
        fmt_local=fmt_local,
        fmt_utc=fmt_utc,
        norm_status=norm_status,
    )
    # логируем все пути, чтобы сразу видеть, что реально поднято
    paths = [r.path for r in app.routes if isinstance(r, APIRoute)]
    logging.warning("ROUTES LOADED: %s", paths)


# favicon под /favicon.ico (браузер не ходит в /static сам)
@app.get("/favicon.ico", include_in_schema=False)
async def favicon_redirect():
    return RedirectResponse(url="/static/favicon.ico")


# хелпер, чтобы не засорять логи devtools-запросом
@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def _devtools_probe():
    return Response(status_code=204)


# служебный роут для быстрой проверки
@app.get("/__routes", include_in_schema=False)
async def __routes():
    return {
        "routes": [
            {
                "path": r.path,
                "methods": sorted(list(r.methods)) if hasattr(r, "methods") else [],
                "name": getattr(r, "name", None),
            }
            for r in app.routes
            if isinstance(r, APIRoute)
        ]
    }


# ---------- helpers ----------

def _safe_zone(tz_str: Optional[str]) -> ZoneInfo:
    """Безопасно возвращает ZoneInfo, по умолчанию Europe/Moscow."""
    try:
        return ZoneInfo(tz_str or "Europe/Moscow")
    except Exception:
        return ZoneInfo("Europe/Moscow")


def fmt_local(dt_utc: datetime, tz_str: str) -> str:
    """Преобразует UTC-время слота в локальное время по TZ."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    local = dt_utc.astimezone(_safe_zone(tz_str))
    return local.strftime("%d.%m %H:%M")


def fmt_utc(dt_utc: datetime) -> str:
    """Красивый вывод UTC (на всякий случай нормализуем tzinfo)."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(timezone.utc).strftime("%d.%m %H:%M")


def norm_status(st) -> Optional[str]:
    """Нормализует статус к простой строке ('FREE'/'PENDING'/'BOOKED')."""
    if st is None:
        return None
    return st.value if hasattr(st, "value") else st


def _status_to_db_filter(status_str: str):
    """
    Конвертирует строку фильтра ('FREE'/'PENDING'/'BOOKED') в то, что хранится в колонке:
    если у модели Enum — вернём Enum, если строка — вернём строку.
    """
    status_upper = (status_str or "").upper()
    enum_candidate = getattr(SlotStatus, status_upper, None)
    return enum_candidate if enum_candidate is not None else status_upper


def _parse_optional_int(val: Optional[str]) -> Optional[int]:
    """Пустая строка/None -> None, число-строка -> int, иначе None."""
    if val is None:
        return None
    s = val.strip()
    if s == "":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------- owner-field helpers (ответственный рекрутёр за город) ----------

CITY_OWNER_FIELD_CANDIDATES = [
    "responsible_recruiter_id",
    "owner_id",
    "recruiter_id",
    "manager_id",
]

def _city_owner_field_name() -> Optional[str]:
    """
    Возвращает имя поля City, куда можно писать id ответственного рекрутёра.
    Поддерживает несколько вариантов названий. Если ни одно не найдено — None.
    """
    insp = sa_inspect(City)
    attrs = set(insp.attrs.keys())
    cols = set(insp.columns.keys()) if hasattr(insp, "columns") else set()
    allowed = attrs | cols
    for name in CITY_OWNER_FIELD_CANDIDATES:
        if name in allowed:
            return name
    return None


# ---------- questions ----------

TEST_LABELS = {
    "test1": "Анкета кандидата",
    "test2": "Инфо-тест",
}

QUESTION_ERROR_MESSAGES = {
    "invalid_json": "Не удалось разобрать JSON с данными вопроса.",
    "duplicate_index": "Для выбранного теста уже существует вопрос с таким порядковым номером.",
    "test_required": "Укажите идентификатор теста.",
    "index_required": "Укажите порядковый номер (целое число).",
}


def _parse_question_payload(payload: Optional[str]) -> Dict[str, object]:
    if not payload:
        return {}
    try:
        data = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _question_kind(data: Dict[str, object]) -> str:
    options = data.get("options") if isinstance(data, dict) else None
    if isinstance(options, list) and options:
        return "choice"
    return "text"


def _correct_option_label(data: Dict[str, object]) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    options = data.get("options")
    correct = data.get("correct")
    if isinstance(options, list) and isinstance(correct, int):
        if 0 <= correct < len(options):
            return str(options[correct])
    return None


async def _list_test_questions() -> List[Dict[str, object]]:
    async with SessionLocal() as s:
        items = (
            await s.scalars(
                select(TestQuestion).order_by(
                    TestQuestion.test_id.asc(), TestQuestion.question_index.asc()
                )
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
                "options_count": len(data.get("options") or []) if isinstance(data, dict) else 0,
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


async def _get_test_question_detail(question_id: int) -> Optional[Dict[str, object]]:
    async with SessionLocal() as s:
        question = await s.get(TestQuestion, question_id)
        if not question:
            return None

    data = _parse_question_payload(question.payload)
    pretty = json.dumps(data or {}, ensure_ascii=False, indent=2, sort_keys=True)
    return {
        "question": question,
        "payload_json": pretty,
        "test_choices": list(TEST_LABELS.items()),
    }


async def _update_test_question(
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

    async with SessionLocal() as s:
        question = await s.get(TestQuestion, question_id)
        if not question:
            return False, "not_found"

        question.title = resolved_title
        question.test_id = clean_test_id
        question.question_index = question_index
        question.payload = normalized_payload
        question.is_active = is_active
        question.updated_at = datetime.now(timezone.utc)

        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            return False, "duplicate_index"

    return True, None


# ---------- dashboard ----------

async def _dashboard_counts() -> Dict[str, int]:
    async with SessionLocal() as s:
        # корректные COUNT-запросы (SQLAlchemy 2.x)
        rec_count = await s.scalar(select(func.count()).select_from(Recruiter))
        city_count = await s.scalar(select(func.count()).select_from(City))
        # одним запросом считаем слоты по статусам
        rows = (await s.execute(select(Slot.status, func.count()).group_by(Slot.status))).all()

    # ключи могут быть как Enum-ами, так и строками — нормализуем к строкам
    by_status: Dict[str, int] = {
        (status.value if hasattr(status, "value") else status): count for status, count in rows
    }
    total = sum(by_status.values())

    # безопасно получаем «ожидаемые» строковые ключи для FREE/PENDING/BOOKED
    def _norm(name: str) -> str:
        obj = getattr(SlotStatus, name, name)
        return obj.value if hasattr(obj, "value") else obj

    status_free = _norm("FREE")
    status_pending = _norm("PENDING")
    status_booked = _norm("BOOKED")

    return {
        "recruiters": rec_count or 0,
        "cities": city_count or 0,
        "slots_total": total,
        "slots_free": by_status.get(status_free, 0),
        "slots_pending": by_status.get(status_pending, 0),
        "slots_booked": by_status.get(status_booked, 0),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    counts = await _dashboard_counts()
    async with SessionLocal() as s:
        recruiters = (await s.scalars(select(Recruiter).order_by(Recruiter.name.asc()))).all()
        cities = (await s.scalars(select(City).order_by(City.name.asc()))).all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "counts": counts, "recruiters": recruiters, "cities": cities},
    )


# ---------- slots ----------

def _paginate(total: int, page: int, per_page: int) -> Tuple[int, int, int]:
    """Возвращает (pages_total, page, offset)."""
    per_page = max(1, min(100, per_page or 20))
    pages_total = max(1, math.ceil(total / per_page)) if total else 1
    page = max(1, min(page or 1, pages_total))
    offset = (page - 1) * per_page
    return pages_total, page, offset


@app.get("/slots", response_class=HTMLResponse)
async def slots_list(
    request: Request,
    recruiter_id: Optional[str] = Query(default=None),   # ← принимаем как строку ("" допустимо)
    status: Optional[str] = Query(default=None),         # ← без жёсткого regex, пустая строка допустима
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    # Нормализуем параметры фильтров
    rid = _parse_optional_int(recruiter_id)
    st = (status or "").strip().upper() or None
    if st not in (None, "FREE", "PENDING", "BOOKED"):
        st = None

    async with SessionLocal() as s:
        # базовый запрос и фильтры
        base = select(Slot)
        if rid is not None:
            base = base.where(Slot.recruiter_id == rid)
        if st:
            base = base.where(Slot.status == _status_to_db_filter(st))

        # total
        total = await s.scalar(select(func.count()).select_from(base.subquery())) or 0

        # пагинация
        pages_total, page, offset = _paginate(total, page, per_page)

        # основная выборка
        q = (
            base.options(selectinload(Slot.recruiter))
            .order_by(Slot.start_utc.desc())
            .offset(offset)
            .limit(per_page)
        )
        slots = (await s.scalars(q)).all()

        # опции для фильтра по рекрутёрам
        recruiters = (await s.scalars(select(Recruiter).order_by(Recruiter.name.asc()))).all()

    return templates.TemplateResponse(
        "slots_list.html",
        {
            "request": request,
            "slots": slots,
            # фильтры/страницы
            "filter_recruiter_id": rid,
            "filter_status": st,
            "page": page,
            "pages_total": pages_total,
            "per_page": per_page,
            "recruiters": recruiters,
        },
    )


@app.get("/slots/new", response_class=HTMLResponse)
async def slots_new(request: Request):
    async with SessionLocal() as s:
        insp = sa_inspect(Recruiter)
        has_active = "active" in insp.columns
        q = select(Recruiter).order_by(Recruiter.name.asc())
        if has_active:
            q = q.where(getattr(Recruiter, "active") == True)  # noqa: E712
        recruiters = (await s.scalars(q)).all()
    return templates.TemplateResponse("slots_new.html", {"request": request, "recruiters": recruiters})


@app.post("/slots/create")
async def slots_create(
    recruiter_id: int = Form(...),
    date: str = Form(...),  # YYYY-MM-DD
    time: str = Form(...),  # HH:MM
):
    # Переводим локальное время рекрутёра в UTC
    async with SessionLocal() as s:
        rec = await s.get(Recruiter, recruiter_id)
        if not rec:
            return RedirectResponse(url="/slots/new", status_code=303)

        try:
            dt_local = datetime.fromisoformat(f"{date}T{time}")  # naive
        except ValueError:
            return RedirectResponse(url="/slots/new", status_code=303)

        dt_local = dt_local.replace(tzinfo=_safe_zone(getattr(rec, "tz", None)))
        dt_utc = dt_local.astimezone(timezone.utc)

        # нормализуем статус FREE (строка или Enum)
        status_free = getattr(SlotStatus, "FREE", "FREE")
        if hasattr(status_free, "value"):
            status_free = status_free.value

        slot = Slot(recruiter_id=recruiter_id, start_utc=dt_utc, status=status_free)
        s.add(slot)
        await s.commit()
    return RedirectResponse(url="/slots", status_code=303)


# ---------- recruiters ----------

def _pick_field(allowed: set, candidates: List[str]) -> Optional[str]:
    """Вернёт первое совпавшее имя атрибута модели из списка кандидатов."""
    for name in candidates:
        if name in allowed:
            return name
    return None


@app.get("/recruiters", response_class=HTMLResponse)
async def recruiters_list(request: Request):
    async with SessionLocal() as s:
        recruiters = list((await s.scalars(select(Recruiter).order_by(Recruiter.name.asc()))).all())

        stats_map: Dict[int, Dict[str, object]] = {}
        city_map: Dict[int, List[Tuple[str, str]]] = {}

        if recruiters:
            rec_ids = [r.id for r in recruiters]

            stats_rows = (await s.execute(
                select(
                    Slot.recruiter_id,
                    func.count().label("total"),
                    func.sum(case((Slot.status == SlotStatus.FREE, 1), else_=0)).label("free"),
                    func.sum(case((Slot.status == SlotStatus.PENDING, 1), else_=0)).label("pending"),
                    func.sum(case((Slot.status == SlotStatus.BOOKED, 1), else_=0)).label("booked"),
                    func.min(case((Slot.status == SlotStatus.FREE, Slot.start_utc), else_=None)).label("next_free"),
                )
                .where(Slot.recruiter_id.in_(rec_ids))
                .group_by(Slot.recruiter_id)
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

            city_rows = (await s.execute(
                select(City.id, City.name, City.tz, City.responsible_recruiter_id)
                .where(City.responsible_recruiter_id.in_(rec_ids))
                .order_by(City.name.asc())
            )).all()

            for row in city_rows:
                city_map.setdefault(row.responsible_recruiter_id, []).append((row.name, row.tz))

    enriched = []
    now = datetime.now(timezone.utc)
    for rec in recruiters:
        stats = stats_map.get(rec.id, {"total": 0, "free": 0, "pending": 0, "booked": 0, "next_free": None})
        next_slot_dt = _ensure_aware(stats.get("next_free"))
        stats["next_free"] = next_slot_dt
        next_local = fmt_local(next_slot_dt, rec.tz or "Europe/Moscow") if next_slot_dt else None
        cities = city_map.get(rec.id, [])
        enriched.append(
            {
                "rec": rec,
                "stats": stats,
                "next_free_local": next_local,
                "next_is_future": (next_slot_dt > now) if next_slot_dt else False,
                "cities": cities,
                "cities_text": " ".join(name.lower() for name, _ in cities),
            }
        )

    return templates.TemplateResponse(
        "recruiters_list.html",
        {"request": request, "recruiters": enriched},
    )


@app.get("/recruiters/new", response_class=HTMLResponse)
async def recruiters_new(request: Request):
    async with SessionLocal() as s:
        cities = (await s.scalars(select(City).order_by(City.name.asc()))).all()
    return templates.TemplateResponse("recruiters_new.html", {"request": request, "cities": cities})


@app.post("/recruiters/create")
async def recruiters_create(
    name: str = Form(...),
    tz: str = Form("Europe/Moscow"),
    telemost: str = Form(""),
    tg_chat_id: str = Form(""),
    active: Optional[str] = Form(None),
    cities: Optional[List[str]] = Form(None),
):
    async with SessionLocal() as s:
        # узнаём доступные поля модели Recruiter (и колонки, и relationship/свойства)
        allowed = set(sa_inspect(Recruiter).attrs.keys())

        # всегда есть name
        kwargs: Dict[str, object] = {"name": name.strip()}

        # TZ (возможные имена)
        tz_field = _pick_field(allowed, ["tz", "timezone", "tz_name", "time_zone"])
        if tz_field:
            kwargs[tz_field] = tz.strip() if tz else "Europe/Moscow"

        # ссылка на созвон (возможные имена)
        link = (telemost or "").strip() or None
        telemost_field = _pick_field(
            allowed,
            ["telemost_url", "telemost", "meet_link", "meet_url", "video_link", "video_url", "link", "room_url"],
        )
        if telemost_field and link:
            kwargs[telemost_field] = link

        # chat id (возможные имена)
        chat_field = _pick_field(allowed, ["tg_chat_id", "telegram_chat_id", "chat_id"])
        if chat_field and tg_chat_id and tg_chat_id.strip().isdigit():
            kwargs[chat_field] = int(tg_chat_id.strip())

        # активность (возможные имена)
        active_field = _pick_field(allowed, ["active", "is_active", "enabled"])
        if active_field:
            kwargs[active_field] = True if active else False

        # создаём безопасно только с поддерживаемыми полями
        rec = Recruiter(**kwargs)
        s.add(rec)
        await s.commit()
        await s.refresh(rec)

        selected_cities: List[int] = []
        if cities:
            for cid in cities:
                if cid and cid.strip().isdigit():
                    selected_cities.append(int(cid.strip()))
        if selected_cities:
            await s.execute(
                update(City)
                .where(City.id.in_(selected_cities))
                .values(responsible_recruiter_id=rec.id)
            )
            await s.commit()
    return RedirectResponse(url="/recruiters", status_code=303)


@app.get("/recruiters/{rec_id}/edit", response_class=HTMLResponse)
async def recruiters_edit(request: Request, rec_id: int):
    async with SessionLocal() as s:
        recruiter = await s.get(Recruiter, rec_id)
        if not recruiter:
            return RedirectResponse(url="/recruiters", status_code=303)

        cities = (await s.scalars(select(City).order_by(City.name.asc()))).all()
        selected_ids = {c.id for c in cities if c.responsible_recruiter_id == rec_id}

    return templates.TemplateResponse(
        "recruiters_edit.html",
        {
            "request": request,
            "recruiter": recruiter,
            "cities": cities,
            "selected_ids": selected_ids,
        },
    )


@app.post("/recruiters/{rec_id}/update")
async def recruiters_update(
    rec_id: int,
    name: str = Form(...),
    tz: str = Form("Europe/Moscow"),
    telemost: str = Form(""),
    tg_chat_id: str = Form(""),
    active: Optional[str] = Form(None),
    cities: Optional[List[str]] = Form(None),
):
    async with SessionLocal() as s:
        rec = await s.get(Recruiter, rec_id)
        if not rec:
            return RedirectResponse(url="/recruiters", status_code=303)

        allowed = set(sa_inspect(Recruiter).attrs.keys())

        rec.name = name.strip()

        tz_field = _pick_field(allowed, ["tz", "timezone", "tz_name", "time_zone"])
        if tz_field:
            setattr(rec, tz_field, tz.strip() if tz else "Europe/Moscow")

        link = (telemost or "").strip() or None
        telemost_field = _pick_field(
            allowed,
            ["telemost_url", "telemost", "meet_link", "meet_url", "video_link", "video_url", "link", "room_url"],
        )
        if telemost_field:
            setattr(rec, telemost_field, link)

        chat_field = _pick_field(allowed, ["tg_chat_id", "telegram_chat_id", "chat_id"])
        if chat_field:
            if tg_chat_id and tg_chat_id.strip().isdigit():
                setattr(rec, chat_field, int(tg_chat_id.strip()))
            else:
                setattr(rec, chat_field, None)

        active_field = _pick_field(allowed, ["active", "is_active", "enabled"])
        if active_field:
            setattr(rec, active_field, True if active else False)

        await s.commit()

        selected: List[int] = []
        if cities:
            for cid in cities:
                if cid and cid.strip().isdigit():
                    selected.append(int(cid.strip()))

        # Очистим старые связи
        await s.execute(
            update(City)
            .where(City.responsible_recruiter_id == rec_id)
            .values(responsible_recruiter_id=None)
        )

        if selected:
            await s.execute(
                update(City)
                .where(City.id.in_(selected))
                .values(responsible_recruiter_id=rec_id)
            )

        await s.commit()

    return RedirectResponse(url="/recruiters", status_code=303)


@app.post("/recruiters/{rec_id}/delete")
async def recruiters_delete(rec_id: int):
    async with SessionLocal() as s:
        rec = await s.get(Recruiter, rec_id)
        if not rec:
            return RedirectResponse(url="/recruiters", status_code=303)

        await s.execute(
            update(City)
            .where(City.responsible_recruiter_id == rec_id)
            .values(responsible_recruiter_id=None)
        )
        await s.delete(rec)
        await s.commit()

    return RedirectResponse(url="/recruiters", status_code=303)


# ---------- cities ----------

@app.get("/cities", response_class=HTMLResponse)
async def cities_list(request: Request):
    async with SessionLocal() as s:
        cities = (await s.scalars(select(City).order_by(City.name.asc()))).all()
        # попытаемся подтянуть ответственных, если поле существует
        owner_field = _city_owner_field_name()
        owners: Dict[int, Optional[int]] = {}
        if owner_field:
            for c in cities:
                owners[c.id] = getattr(c, owner_field, None)
        # рекрутёры для отображения
        recruiters = (await s.scalars(select(Recruiter).order_by(Recruiter.name.asc()))).all()
        rec_map = {r.id: r for r in recruiters}
    return templates.TemplateResponse(
        "cities_list.html",
        {
            "request": request,
            "cities": cities,
            "owner_field": _city_owner_field_name(),
            "owners": owners,
            "rec_map": rec_map,
        },
    )


@app.get("/cities/new", response_class=HTMLResponse)
async def cities_new(request: Request):
    return templates.TemplateResponse("cities_new.html", {"request": request})


@app.post("/cities/create")
async def cities_create(
    name: str = Form(...),
    tz: str = Form("Europe/Moscow"),
):
    async with SessionLocal() as s:
        city = City(name=name.strip(), tz=tz.strip() if tz else "Europe/Moscow")
        s.add(city)
        await s.commit()
    return RedirectResponse(url="/cities", status_code=303)


# --- КАНБАН: ответственные рекрутёры за города ---

@app.get("/cities/owners", response_class=HTMLResponse)
async def cities_owners_board(request: Request):
    owner_field = _city_owner_field_name()
    async with SessionLocal() as s:
        recruiters = (await s.scalars(select(Recruiter).order_by(Recruiter.name.asc()))).all()
        cities = (await s.scalars(select(City).order_by(City.name.asc()))).all()
        # подготовим маппинг город -> owner_id (если поле есть)
        owners: Dict[int, Optional[int]] = {}
        if owner_field:
            for c in cities:
                owners[c.id] = getattr(c, owner_field, None)
    return templates.TemplateResponse(
        "cities_owners.html",
        {
            "request": request,
            "recruiters": recruiters,
            "cities": cities,
            "owner_field_exists": owner_field is not None,
            "owner_field": owner_field,
            "owners": owners,
        },
    )


@app.post("/cities/owners/assign")
async def cities_owner_assign(request: Request):
    """
    Принимает JSON: {"city_id": 1, "recruiter_id": 2|null}
    """
    owner_field = _city_owner_field_name()
    if not owner_field:
        return JSONResponse({"ok": False, "error": "Owner field is missing on City model."}, status_code=400)

    try:
        payload = await request.json()
        city_id = int(payload.get("city_id"))
        recruiter_id = payload.get("recruiter_id", None)
        rec_id_val: Optional[int] = None
        if recruiter_id not in (None, "", "null"):
            rec_id_val = int(recruiter_id)
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid payload"}, status_code=400)

    async with SessionLocal() as s:
        city = await s.get(City, city_id)
        if not city:
            return JSONResponse({"ok": False, "error": "City not found"}, status_code=404)

        if rec_id_val is not None:
            rec = await s.get(Recruiter, rec_id_val)
            if not rec:
                return JSONResponse({"ok": False, "error": "Recruiter not found"}, status_code=404)

        setattr(city, owner_field, rec_id_val)
        await s.commit()

    return JSONResponse({"ok": True})


# ---------- questions UI ----------


@app.get("/questions", response_class=HTMLResponse)
async def questions_list(request: Request):
    tests = await _list_test_questions()
    return templates.TemplateResponse(
        "questions_list.html",
        {"request": request, "tests": tests},
    )


@app.get("/questions/{question_id}/edit", response_class=HTMLResponse)
async def questions_edit(request: Request, question_id: int, err: Optional[str] = Query(None)):
    detail = await _get_test_question_detail(question_id)
    if not detail:
        return RedirectResponse(url="/questions", status_code=303)

    error_message = QUESTION_ERROR_MESSAGES.get(err or "")
    return templates.TemplateResponse(
        "questions_edit.html",
        {
            "request": request,
            "detail": detail,
            "error_message": error_message,
        },
    )


@app.post("/questions/{question_id}/update")
async def questions_update(
    question_id: int,
    title: str = Form(""),
    test_id: str = Form(...),
    question_index: str = Form(...),
    payload: str = Form(...),
    is_active: Optional[str] = Form(None),
):
    index_value = _parse_optional_int(question_index)
    if index_value is None or index_value < 1:
        return RedirectResponse(url=f"/questions/{question_id}/edit?err=index_required", status_code=303)

    success, error = await _update_test_question(
        question_id,
        title=title,
        test_id=test_id,
        question_index=index_value,
        payload=payload,
        is_active=bool(is_active),
    )
    if not success:
        if error == "not_found":
            return RedirectResponse(url="/questions", status_code=303)
        return RedirectResponse(url=f"/questions/{question_id}/edit?err={error}", status_code=303)

    return RedirectResponse(url="/questions", status_code=303)


# ---------- templates (шаблоны по городам + глобальные) ----------

@app.get("/templates", response_class=HTMLResponse)
async def templates_list(request: Request):
    async with SessionLocal() as s:
        q = (
            select(Template)
            .options(selectinload(Template.city))
            .order_by(Template.key.asc())
        )
        items = (await s.scalars(q)).all()
        cities = (await s.scalars(select(City).order_by(City.name.asc()))).all()
    return templates.TemplateResponse(
        "templates_list.html",
        {"request": request, "items": items, "cities": cities},
    )


@app.get("/templates/new", response_class=HTMLResponse)
async def templates_new(request: Request):
    async with SessionLocal() as s:
        cities = (await s.scalars(select(City).order_by(City.name.asc()))).all()
    return templates.TemplateResponse("templates_new.html", {"request": request, "cities": cities})


@app.post("/templates/create")
async def templates_create(
    key: str = Form(...),
    text: str = Form(...),
    city_id: Optional[str] = Form(None),     # ← принимаем как строку
    is_global: Optional[str] = Form(None),
):
    # если отметили глобальный — city_id игнорируем
    if is_global:
        city_id_val: Optional[int] = None
    else:
        # для неглобальных требуется валидный city_id
        city_id_val = _parse_optional_int(city_id)
        if city_id_val is None:
            return RedirectResponse(url="/templates/new?err=city_required", status_code=303)

    async with SessionLocal() as s:
        tmpl = Template(city_id=city_id_val, key=key.strip(), content=text)
        s.add(tmpl)
        await s.commit()
    return RedirectResponse(url="/templates", status_code=303)


@app.get("/templates/{tmpl_id}/edit", response_class=HTMLResponse)
async def templates_edit(request: Request, tmpl_id: int):
    async with SessionLocal() as s:
        tmpl = await s.get(Template, tmpl_id)
        if not tmpl:
            return RedirectResponse(url="/templates", status_code=303)
        cities = (await s.scalars(select(City).order_by(City.name.asc()))).all()
    return templates.TemplateResponse(
        "templates_edit.html",
        {"request": request, "tmpl": tmpl, "cities": cities},
    )


@app.post("/templates/{tmpl_id}/update")
async def templates_update(
    tmpl_id: int,
    key: str = Form(...),
    text: str = Form(...),
    city_id: Optional[str] = Form(None),     # ← тоже строка
    is_global: Optional[str] = Form(None),
):
    if is_global:
        city_id_val: Optional[int] = None
    else:
        city_id_val = _parse_optional_int(city_id)
        if city_id_val is None:
            return RedirectResponse(url=f"/templates/{tmpl_id}/edit?err=city_required", status_code=303)

    async with SessionLocal() as s:
        tmpl = await s.get(Template, tmpl_id)
        if not tmpl:
            return RedirectResponse(url="/templates", status_code=303)
        tmpl.city_id = city_id_val
        tmpl.key = key.strip()
        tmpl.content = text
        await s.commit()
    return RedirectResponse(url="/templates", status_code=303)


@app.post("/templates/{tmpl_id}/delete")
async def templates_delete(tmpl_id: int):
    async with SessionLocal() as s:
        await s.execute(delete(Template).where(Template.id == tmpl_id))
        await s.commit()
    return RedirectResponse(url="/templates", status_code=303)


# ---------- JSON API для проверки/бота ----------

@app.get("/api/health")
async def api_health():
    counts = await _dashboard_counts()
    return counts


@app.get("/api/recruiters")
async def api_recruiters():
    async with SessionLocal() as s:
        recs = (await s.scalars(select(Recruiter).order_by(Recruiter.id.asc()))).all()
    return JSONResponse([
        {
            "id": r.id,
            "name": r.name,
            "tz": getattr(r, "tz", None),
            "tg_chat_id": getattr(r, "tg_chat_id", None),
            "active": getattr(r, "active", True),
        }
        for r in recs
    ])


@app.get("/api/cities")
async def api_cities():
    async with SessionLocal() as s:
        cities = (await s.scalars(select(City).order_by(City.id.asc()))).all()
    # попытаемся вернуть owner_id, если поле есть
    owner_field = _city_owner_field_name()
    return JSONResponse([
        {
            "id": c.id,
            "name": c.name,
            "tz": getattr(c, "tz", None),
            "owner_recruiter_id": (getattr(c, owner_field) if owner_field else None)
        }
        for c in cities
    ])


@app.get("/api/slots")
async def api_slots(
    recruiter_id: Optional[str] = None,   # ← строка, "" допустимо
    status: Optional[str] = None,         # ← строка, "" допустимо
    limit: int = 100,
):
    rid = _parse_optional_int(recruiter_id)
    st = (status or "").strip().upper() or None
    if st not in (None, "FREE", "PENDING", "BOOKED"):
        st = None

    async with SessionLocal() as s:
        q = select(Slot).options(selectinload(Slot.recruiter)).order_by(Slot.start_utc.asc())
        if rid is not None:
            q = q.where(Slot.recruiter_id == rid)
        if st:
            q = q.where(Slot.status == _status_to_db_filter(st))
        if limit:
            q = q.limit(max(1, min(500, limit)))
        slots = (await s.scalars(q)).all()

    return JSONResponse([
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
    ])


@app.get("/api/templates")
async def api_templates(city_id: Optional[int] = None, key: Optional[str] = None):
    """
    Поведение:
      - если заданы city_id и key: вернуть городской, а если нет — глобальный (fallback).
      - если задан только city_id: вернуть все городские + все глобальные (с флагом is_global).
      - если задан только key: вернуть список всех (где key совпадает), глобальные помечены.
      - если ничего не задано: вернуть всё.
    """
    async with SessionLocal() as s:
        if city_id is not None and key is not None:
            # сначала городской
            q_city = select(Template).where(Template.city_id == city_id, Template.key == key)
            obj = (await s.scalars(q_city)).first()
            if obj:
                return JSONResponse({
                    "found": True,
                    "id": obj.id,
                    "city_id": obj.city_id,
                    "key": obj.key,
                    "text": obj.content,
                    "is_global": obj.city_id is None,
                }, status_code=200)
            # фоллбек: глобальный
            q_glob = select(Template).where(Template.city_id.is_(None), Template.key == key)
            obj = (await s.scalars(q_glob)).first()
            if obj:
                return JSONResponse({
                    "found": True,
                    "id": obj.id,
                    "city_id": obj.city_id,
                    "key": obj.key,
                    "text": obj.content,
                    "is_global": True,
                }, status_code=200)
            return JSONResponse({"found": False}, status_code=404)

        # наборы
        q = select(Template)
        if city_id is not None:
            # все городские + все глобальные
            city_items = (await s.scalars(q.where(Template.city_id == city_id))).all()
            glob_items = (await s.scalars(q.where(Template.city_id.is_(None)))).all()
            items = city_items + glob_items
        elif key is not None:
            items = (await s.scalars(q.where(Template.key == key))).all()
        else:
            items = (await s.scalars(q)).all()

    return JSONResponse([
        {
            "id": t.id,
            "city_id": t.city_id,
            "key": t.key,
            "text": t.content,
            "is_global": t.city_id is None,
        }
        for t in items
    ])


# Helper endpoint to suggest common template keys for the UI
@app.get("/api/template_keys")
async def api_template_keys():
    # Commonly used keys for city templates (used by the datalist in the UI)
    return JSONResponse([
        "invite_interview",
        "confirm_interview",
        "after_approval",
        "intro_day_reminder",
        "confirm_2h",
        "reminder_1h",
        "followup_missed",
        "after_meeting",
        "slot_rejected",
    ])


# Доп. JSON для фронтового контроля канбана
@app.get("/api/city_owners")
async def api_city_owners():
    owner_field = _city_owner_field_name()
    if not owner_field:
        return JSONResponse({"ok": False, "error": "Owner field is missing on City model."}, status_code=400)

    async with SessionLocal() as s:
        cities = (await s.scalars(select(City))).all()
        return JSONResponse({
            "ok": True,
            "owners": {c.id: getattr(c, owner_field, None) for c in cities}
        })
