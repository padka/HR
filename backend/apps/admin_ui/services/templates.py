from __future__ import annotations

import secrets
import string
import time
from typing import Dict, List, Optional, Sequence

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError

from backend.core.db import async_session
from backend.domain.models import City, Template
from backend.domain.template_stages import CITY_TEMPLATE_STAGES, STAGE_DEFAULTS

__all__ = [
    "get_stage_templates",
    "stage_payload_for_ui",
    "templates_overview",
    "update_templates_for_city",
    "list_templates",
    "generate_template_key",
    "create_template",
    "get_template",
    "update_template",
    "delete_template",
    "api_templates_payload",
]


STAGE_KEYS: List[str] = [stage.key for stage in CITY_TEMPLATE_STAGES]


KEY_ALPHABET = string.ascii_lowercase + string.digits


def generate_template_key(prefix: str = "tmpl") -> str:
    """Generate a pseudo-random key for templates."""

    stamp = format(int(time.time() * 1000), "x")
    random_part = "".join(secrets.choice(KEY_ALPHABET) for _ in range(6))
    return f"{prefix}_{stamp}_{random_part}"


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
    async with async_session() as session:
        cities = (await session.scalars(select(City).order_by(City.name.asc()))).all()
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


async def list_templates() -> Dict[str, object]:
    overview = await templates_overview()
    return overview


async def create_template(text: str, city_id: Optional[int], *, key: Optional[str] = None) -> str:
    """Create a template, auto-generating a key when not provided."""

    attempts = 0
    async with async_session() as session:
        while True:
            attempts += 1
            final_key = (key or generate_template_key()).strip()
            session.add(Template(city_id=city_id, key=final_key, content=text))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                if key is not None or attempts >= 5:
                    raise
                # Retry with a freshly generated key
                key = None
                continue
            return final_key


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
            city_items = (await session.scalars(query.where(Template.city_id == city_id))).all()
            global_items = (await session.scalars(query.where(Template.city_id.is_(None)))).all()
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
