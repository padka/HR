from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.apps.admin_ui.security import Principal, require_admin, require_csrf_token, require_principal
from backend.apps.admin_ui.services.builder_graph import apply_test_builder_graph, get_test_builder_graph
from backend.apps.admin_ui.services.message_templates import (
    create_message_template,
    delete_message_template,
    get_template_history,
    list_message_templates,
    update_message_template,
)
from backend.apps.admin_ui.services.message_templates_presets import list_known_template_keys, known_template_presets
from backend.apps.admin_ui.services.questions import (
    clone_test_question,
    create_test_question,
    get_test_question_detail,
    list_test_questions,
    reorder_test_questions,
    update_test_question,
)
from backend.apps.admin_ui.services.test_builder_preview import preview_test_builder_graph
from backend.core.audit import log_audit_action
from backend.core.db import async_session
from backend.domain.models import MessageTemplate, recruiter_city_association

logger = logging.getLogger(__name__)

router = APIRouter(tags=["content_api"])

RECRUITER_EDITABLE_TEMPLATE_KEYS = {
    "approved_msg",
    "att_confirmed_ack",
    "att_confirmed_link",
    "att_declined",
    "att_declined_reason_prompt",
    "candidate_rejection",
    "confirm_2h",
    "confirm_3h",
    "confirm_6h",
    "interview_confirmed_candidate",
    "interview_invite_details",
    "interview_remind_confirm_2h",
    "reminder_10m",
    "intro_day_invitation",
    "intro_day_invite",
    "intro_day_invite_city",
    "intro_day_remind_2h",
    "intro_day_reminder",
    "manual_schedule_prompt",
    "result_fail",
    "slot_proposal_candidate",
    "t1_done",
    "t1_intro",
    "t2_intro",
    "t2_result",
}


async def _recruiter_template_city_ids(principal: Principal) -> set[int]:
    if principal.type != "recruiter":
        return set()
    async with async_session() as session:
        rows = await session.execute(
            select(recruiter_city_association.c.city_id).where(
                recruiter_city_association.c.recruiter_id == principal.id
            )
        )
    return {int(row[0]) for row in rows if row[0] is not None}


async def _check_template_access(
    principal: Principal,
    *,
    city_id: int | None,
    key: str | None,
) -> None:
    if principal.type == "admin":
        return
    if principal.type != "recruiter":
        raise HTTPException(status_code=403, detail={"message": "Forbidden"})
    if city_id is None:
        raise HTTPException(
            status_code=403,
            detail={"message": "Рекрутер может редактировать только шаблоны, привязанные к городу."},
        )
    if key and key not in RECRUITER_EDITABLE_TEMPLATE_KEYS:
        raise HTTPException(
            status_code=403,
            detail={"message": "Этот шаблон доступен только администратору."},
        )
    allowed_city_ids = await _recruiter_template_city_ids(principal)
    if int(city_id) not in allowed_city_ids:
        raise HTTPException(status_code=403, detail={"message": "Город недоступен для рекрутёра."})


async def _load_template_or_404(template_id: int) -> MessageTemplate:
    async with async_session() as session:
        template = await session.get(MessageTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail={"message": "Шаблон не найден"})
    return template


def _template_updated_by(principal: Principal, request: Request) -> str:
    actor = getattr(request.state, "admin_username", None)
    if actor:
        return str(actor)
    return "admin" if principal.type == "admin" else f"recruiter:{principal.id}"


def _template_permissions_payload(
    principal: Principal,
    *,
    editable_city_ids: set[int],
) -> dict[str, object]:
    return {
        "role": principal.type,
        "can_manage_global": principal.type == "admin",
        "editable_city_ids": sorted(editable_city_ids),
        "editable_keys": sorted(RECRUITER_EDITABLE_TEMPLATE_KEYS) if principal.type == "recruiter" else [],
    }


def _template_can_edit(
    principal: Principal,
    *,
    city_id: int | None,
    key: str | None,
    editable_city_ids: set[int],
) -> bool:
    if principal.type == "admin":
        return True
    if city_id is None:
        return False
    return int(city_id) in editable_city_ids and (key or "") in RECRUITER_EDITABLE_TEMPLATE_KEYS


@router.get("/message-templates")
async def api_message_templates(
    city: Optional[str] = Query(default=None),
    key: Optional[str] = Query(default=None),
    channel: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    principal: Principal = Depends(require_principal),
):
    editable_city_ids = await _recruiter_template_city_ids(principal)
    payload = await list_message_templates(
        city=city,
        key_query=key,
        channel=channel,
        status=status,
        allowed_city_ids=editable_city_ids if principal.type == "recruiter" else None,
        allowed_keys=RECRUITER_EDITABLE_TEMPLATE_KEYS if principal.type == "recruiter" else None,
        include_global=True,
    )
    encoded = jsonable_encoder(payload)
    templates = list(encoded.get("templates") or [])
    for item in templates:
        if not isinstance(item, dict):
            continue
        city_id = item.get("city_id")
        key_value = item.get("key")
        item["scope"] = "global" if city_id in (None, "") else "city"
        item["scope_label"] = "Глобальный" if city_id in (None, "") else "Городской"
        item["can_edit"] = _template_can_edit(
            principal,
            city_id=int(city_id) if city_id not in (None, "") else None,
            key=str(key_value or "") or None,
            editable_city_ids=editable_city_ids,
        )
        item["can_delete"] = bool(item["can_edit"])
    encoded["permissions"] = _template_permissions_payload(
        principal,
        editable_city_ids=editable_city_ids,
    )
    return JSONResponse(encoded)


@router.post("/message-templates", status_code=201)
async def api_create_message_template(
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    city_id = data.get("city_id")
    try:
        city_value = None if city_id in (None, "", "null") else int(city_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail={"message": "Некорректный город"}) from exc
    await _check_template_access(
        principal,
        city_id=city_value,
        key=str(data.get("key") or "") or None,
    )
    ok, errors, template = await create_message_template(
        key=str(data.get("key") or ""),
        locale=str(data.get("locale") or "ru"),
        channel=str(data.get("channel") or "tg"),
        body=str(data.get("body") or ""),
        is_active=bool(data.get("is_active", True)),
        city_id=city_value,
        updated_by=_template_updated_by(principal, request),
        version=data.get("version"),
    )
    if not ok:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)
    await log_audit_action(
        "template_create",
        "message_template",
        template.id if template else None,
        changes={"key": data.get("key"), "city_id": data.get("city_id")},
    )
    return JSONResponse({"ok": True, "id": template.id if template else None}, status_code=201)


@router.put("/message-templates/{template_id}")
async def api_update_message_template(
    template_id: int,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    current_template = await _load_template_or_404(template_id)
    await _check_template_access(
        principal,
        city_id=current_template.city_id,
        key=current_template.key,
    )
    city_id = data.get("city_id")
    try:
        city_value = None if city_id in (None, "", "null") else int(city_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail={"message": "Некорректный город"}) from exc
    await _check_template_access(
        principal,
        city_id=city_value,
        key=str(data.get("key") or current_template.key) or None,
    )
    ok, errors, template = await update_message_template(
        template_id=template_id,
        key=str(data.get("key") or ""),
        locale=str(data.get("locale") or "ru"),
        channel=str(data.get("channel") or "tg"),
        body=str(data.get("body") or ""),
        is_active=bool(data.get("is_active", True)),
        city_id=city_value,
        updated_by=_template_updated_by(principal, request),
        expected_version=data.get("version"),
    )
    if not ok:
        return JSONResponse({"ok": False, "errors": errors}, status_code=400)
    await log_audit_action(
        "template_update",
        "message_template",
        template_id,
        changes={"key": data.get("key"), "city_id": data.get("city_id")},
    )
    return JSONResponse({"ok": True, "id": template.id if template else None})


@router.delete("/message-templates/{template_id}")
async def api_delete_message_template(
    template_id: int,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    template = await _load_template_or_404(template_id)
    await _check_template_access(
        principal,
        city_id=template.city_id,
        key=template.key,
    )
    await delete_message_template(template_id)
    await log_audit_action("template_delete", "message_template", template_id)
    return JSONResponse({"ok": True})


@router.get("/message-templates/{template_id}/history")
async def api_message_template_history(
    template_id: int,
    principal: Principal = Depends(require_principal),
):
    template = await _load_template_or_404(template_id)
    await _check_template_access(
        principal,
        city_id=template.city_id,
        key=template.key,
    )
    history = await get_template_history(template_id)
    payload = [
        {
            "id": item.id,
            "version": item.version,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "updated_by": item.updated_by,
            "body": item.body_md,
        }
        for item in history
    ]
    return JSONResponse({"items": payload})


@router.get("/questions")
async def api_questions(_: Principal = Depends(require_admin)):
    return JSONResponse(await list_test_questions())


@router.post("/questions", status_code=201)
async def api_question_create(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    ok, question_id, error = await create_test_question(
        title=str(data.get("title") or ""),
        test_id=str(data.get("test_id") or ""),
        question_index=int(data.get("question_index")) if data.get("question_index") is not None else None,
        payload=str(data.get("payload") or ""),
        is_active=bool(data.get("is_active", True)),
    )
    if not ok:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    return JSONResponse({"ok": True, "id": question_id}, status_code=201)


@router.get("/questions/{question_id}")
async def api_question_detail(
    question_id: int,
    _: Principal = Depends(require_admin),
):
    detail = await get_test_question_detail(question_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Question not found")
    question = detail.get("question")
    return JSONResponse(
        {
            "id": question.id,
            "title": question.title,
            "test_id": question.test_id,
            "question_index": question.question_index,
            "payload": detail.get("payload_json"),
            "is_active": question.is_active,
            "test_choices": detail.get("test_choices"),
        }
    )


@router.put("/questions/{question_id}")
async def api_question_update(
    question_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    ok, error = await update_test_question(
        question_id,
        title=str(data.get("title") or ""),
        test_id=str(data.get("test_id") or ""),
        question_index=int(data.get("question_index") or 0),
        payload=str(data.get("payload") or ""),
        is_active=bool(data.get("is_active", True)),
    )
    if not ok:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    return JSONResponse({"ok": True})


@router.post("/questions/{question_id}/clone")
async def api_question_clone(
    question_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    ok, new_id, error = await clone_test_question(question_id)
    if not ok:
        status_code = 404 if error == "not_found" else 400
        return JSONResponse({"ok": False, "error": error}, status_code=status_code)
    return JSONResponse({"ok": True, "id": new_id})


@router.post("/questions/reorder")
async def api_questions_reorder(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    test_id = str(data.get("test_id") or "")
    order = data.get("order")
    if not isinstance(order, list):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    ok, error = await reorder_test_questions(
        test_id=test_id,
        order=order,  # type: ignore[arg-type]
    )
    if not ok:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    return JSONResponse({"ok": True})


@router.get("/test-builder/graph")
async def api_test_builder_graph(
    test_id: str = Query(...),
    _: Principal = Depends(require_admin),
):
    clean = str(test_id or "").strip()
    if not clean:
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    graph, updated_at = await get_test_builder_graph(test_id=clean)
    return JSONResponse(
        {
            "ok": True,
            "test_id": clean,
            "graph": graph,
            "updated_at": updated_at.isoformat() if updated_at else None,
        }
    )


@router.post("/test-builder/graph/apply")
async def api_test_builder_graph_apply(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    test_id = str(data.get("test_id") or "")
    graph = data.get("graph")
    if not isinstance(graph, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    ok, error = await apply_test_builder_graph(test_id=test_id, graph=graph)
    if not ok:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    return JSONResponse({"ok": True})


@router.post("/test-builder/graph/preview")
async def api_test_builder_graph_preview(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    test_id = str(data.get("test_id") or "").strip()
    graph = data.get("graph")
    answers_raw = data.get("answers") or []

    if not isinstance(graph, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})
    if not isinstance(answers_raw, list):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    answers = [str(item or "") for item in answers_raw]
    ok, payload, error = await preview_test_builder_graph(
        test_id=test_id,
        graph=graph,
        answers=answers,
    )
    if not ok:
        return JSONResponse({"ok": False, "error": error}, status_code=400)
    return JSONResponse(payload)


@router.get("/templates/list")
async def api_templates_list(
    _: Principal = Depends(require_admin),
):
    async with async_session() as session:
        rows = await session.execute(
            select(MessageTemplate)
            .options(selectinload(MessageTemplate.city))
            .order_by(MessageTemplate.key, MessageTemplate.id)
        )
        templates = list(rows.scalars())

    custom_templates = []
    for template in templates:
        city_name = None
        is_global = template.city_id is None
        if template.city and hasattr(template.city, "name"):
            city_name = getattr(template.city, "name_plain", template.city.name) or template.city.name
        custom_templates.append({
            "id": template.id,
            "key": template.key,
            "city_id": template.city_id,
            "city_name": city_name,
            "city_name_plain": city_name,
            "is_global": is_global,
            "preview": (template.body_md or "")[:120],
            "length": len(template.body_md or ""),
        })
    return JSONResponse({"custom_templates": custom_templates, "overview": None})


@router.get("/templates/{template_id:int}")
async def api_template_detail(
    template_id: int,
    _: Principal = Depends(require_admin),
):
    async with async_session() as session:
        template = await session.get(MessageTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return JSONResponse({
        "id": template.id,
        "key": template.key,
        "text": template.body_md or "",
        "city_id": template.city_id,
        "is_global": template.city_id is None,
        "is_active": template.is_active,
    })


@router.put("/templates/{template_id:int}")
async def api_template_update(
    template_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    async with async_session() as session:
        template = await session.get(MessageTemplate, template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if "key" in data and data["key"]:
            template.key = str(data["key"]).strip()
        if "text" in data:
            template.body_md = str(data["text"] or "")
        if "city_id" in data:
            template.city_id = int(data["city_id"]) if data["city_id"] else None
        if "is_active" in data:
            template.is_active = bool(data["is_active"])
        template.updated_by = "admin"
        template.updated_at = datetime.now(timezone.utc)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return JSONResponse(
                {"ok": False, "error": "Шаблон для выбранного города и типа уже существует."},
                status_code=400,
            )
    await log_audit_action(
        "template_update",
        "message_template",
        template_id,
        changes={"key": data.get("key"), "city_id": data.get("city_id")},
    )
    return JSONResponse({"ok": True, "id": template.id})


@router.delete("/templates/{template_id:int}")
async def api_template_delete(
    template_id: int,
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    async with async_session() as session:
        template = await session.get(MessageTemplate, template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        template_key = template.key
        await session.delete(template)
        await session.commit()
    await log_audit_action("template_delete", "message_template", template_id, changes={"key": template_key})
    return JSONResponse({"ok": True})


@router.post("/templates", status_code=201)
async def api_template_create(
    request: Request,
    _: Principal = Depends(require_admin),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Invalid payload"})

    key_value = str(data.get("key") or "").strip()
    body_value = str(data.get("text") or "").strip()
    locale_value = str(data.get("locale") or "ru").strip() or "ru"
    channel_value = str(data.get("channel") or "tg").strip() or "tg"
    version_value = data.get("version")
    try:
        version_value = int(version_value) if version_value is not None else 1
    except (TypeError, ValueError):
        version_value = 1
    is_active_value = bool(data.get("is_active", True))

    if not body_value:
        return JSONResponse({"ok": False, "error": "Введите текст шаблона."}, status_code=400)

    city_id = data.get("city_id")
    if city_id is not None:
        try:
            city_id = int(city_id)
        except (TypeError, ValueError):
            city_id = None

    if not key_value:
        key_value = f"custom_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    revived_id: Optional[int] = None
    created_id: Optional[int] = None

    async with async_session() as session:
        existing = await session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.key == key_value,
                MessageTemplate.locale == locale_value,
                MessageTemplate.channel == channel_value,
                MessageTemplate.city_id == city_id,
                MessageTemplate.version == version_value,
            )
        )
        if existing:
            if not existing.is_active:
                existing.body_md = body_value
                existing.is_active = is_active_value
                existing.updated_by = "admin"
                existing.updated_at = datetime.now(timezone.utc)
                await session.commit()
                revived_id = existing.id
            else:
                return JSONResponse(
                    {"ok": False, "error": "Шаблон для выбранного города и типа уже существует."},
                    status_code=400,
                )
        else:
            template = MessageTemplate(
                key=key_value,
                locale=locale_value,
                channel=channel_value,
                body_md=body_value,
                version=version_value,
                is_active=is_active_value,
                city_id=city_id,
                updated_by="admin",
            )
            session.add(template)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return JSONResponse(
                    {"ok": False, "error": "Шаблон для выбранного города и типа уже существует."},
                    status_code=400,
                )
            await session.refresh(template)
            created_id = template.id
    if revived_id is not None:
        await log_audit_action(
            "template_revive",
            "message_template",
            revived_id,
            changes={"key": key_value, "city_id": city_id},
        )
        return JSONResponse({"ok": True, "id": revived_id, "revived": True}, status_code=201)

    assert created_id is not None
    await log_audit_action(
        "template_create",
        "message_template",
        created_id,
        changes={"key": key_value, "city_id": city_id},
    )
    return JSONResponse({"ok": True, "id": created_id}, status_code=201)


@router.get("/template_keys")
async def api_template_keys():
    return JSONResponse(list_known_template_keys())


@router.get("/template_presets")
async def api_template_presets():
    presets_list = known_template_presets()

    def _sanitize(value: str) -> str:
        return value.encode("utf-8", "ignore").decode("utf-8") if value else value

    result = {}
    for item in presets_list:
        result[item["key"]] = _sanitize(item["text"])
    return JSONResponse(result)


@router.get("/message-templates/context-keys")
async def api_message_template_context_keys(
    principal: Principal = Depends(require_principal),
):
    del principal
    from backend.domain.template_contexts import TEMPLATE_CONTEXTS

    return JSONResponse(TEMPLATE_CONTEXTS)


@router.post("/message-templates/preview")
async def api_message_template_preview(
    request: Request,
    principal: Principal = Depends(require_principal),
):
    _ = await require_csrf_token(request)
    data = await request.json()
    text = str(data.get("text") or "")
    key = str(data.get("key") or "")
    city_id_raw = data.get("city_id")
    city_id = None
    if city_id_raw not in (None, "", "null"):
        try:
            city_id = int(city_id_raw)
        except (TypeError, ValueError):
            city_id = None
    await _check_template_access(
        principal,
        city_id=city_id,
        key=key or None,
    )

    from backend.apps.admin_ui.services.message_templates import render_message_template_preview

    try:
        rendered = await render_message_template_preview(text=text, key=key, city_id=city_id)
        return JSONResponse({"ok": True, "html": rendered})
    except Exception as exc:
        logger.exception("message_template.preview.failed")
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
