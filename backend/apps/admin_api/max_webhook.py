"""Bounded MAX webhook ingress for shared candidate journey orchestration."""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from backend.apps.admin_api.max_candidate_chat import (
    activate_max_chat_handoff,
    book_max_chat_slot,
    bootstrap_max_chat_principal,
    is_max_chat_active,
    process_max_chat_callback,
    process_max_chat_text_answer,
    resolve_max_chat_context,
    send_max_chat_prompt,
    wants_max_chat_handoff,
)
from backend.apps.admin_api.max_launch import MaxLaunchError
from backend.apps.bot.services.broadcast import notify_recruiters_manual_availability
from backend.apps.bot.services.slot_flow import _parse_manual_availability_window
from backend.core.db import async_session
from backend.core.messenger.bootstrap import ensure_max_adapter
from backend.core.messenger.protocol import InlineButton
from backend.core.settings import Settings, get_settings
from backend.domain.candidates.models import ChatMessage, User
from backend.domain.candidates.services import (
    bind_max_to_candidate,
    log_inbound_max_message,
    log_outbound_max_message,
    mark_manual_slot_requested_for_candidate,
    save_manual_slot_response_for_user,
)
from backend.domain.candidates.status import CandidateStatus
from backend.domain.candidates.status_service import apply_candidate_status
from backend.domain.repositories import find_city_by_plain_name, register_callback

logger = logging.getLogger(__name__)

router = APIRouter(tags=["max"])


class MaxWebhookAck(BaseModel):
    ok: bool = True
    handled: bool = True
    update_type: str | None = None
    duplicate: bool = False
    ignored_reason: str | None = None


def _verify_max_webhook_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_max_bot_api_secret: Annotated[
        str | None,
        Header(alias="X-Max-Bot-Api-Secret"),
    ] = None,
) -> None:
    expected = str(
        getattr(settings, "max_bot_api_secret", "")
        or getattr(settings, "max_webhook_secret", "")
        or ""
    ).strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX webhook secret is not configured",
        )
    actual = str(x_max_bot_api_secret or "").strip()
    if not actual or not hmac.compare_digest(actual, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid MAX webhook secret",
        )


def _stable_client_request_id(prefix: str, raw_value: str | None) -> str:
    normalized = f"max:{prefix}:{str(raw_value or '').strip()}"
    if len(normalized) <= 64 and normalized.rstrip(":") != "max":
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"max:{prefix}:{digest[:48]}"


def _update_type(payload: dict[str, Any]) -> str:
    return str(payload.get("update_type") or "").strip().lower()


def _extract_user(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message") or {}
    callback = payload.get("callback") or {}
    recipient = message.get("recipient") if isinstance(message, dict) else {}
    candidates = [
        payload.get("user"),
        callback.get("user") if isinstance(callback, dict) else None,
        callback.get("sender") if isinstance(callback, dict) else None,
        recipient.get("dialog_with_user") if isinstance(recipient, dict) else None,
        payload.get("sender"),
        message.get("sender") if isinstance(message, dict) else None,
        recipient if isinstance(recipient, dict) and recipient.get("user_id") is not None else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return {}


def _extract_user_id(payload: dict[str, Any]) -> str | None:
    user = _extract_user(payload)
    raw = user.get("user_id") or user.get("id")
    if raw is None:
        return None
    normalized = str(raw).strip()
    return normalized or None


def _extract_username(payload: dict[str, Any]) -> str | None:
    user = _extract_user(payload)
    normalized = str(user.get("username") or "").strip()
    return normalized or None


def _extract_display_name(payload: dict[str, Any]) -> str | None:
    user = _extract_user(payload)
    display = str(
        user.get("name")
        or user.get("first_name")
        or user.get("display_name")
        or ""
    ).strip()
    if display:
        return display
    username = _extract_username(payload)
    return username


def _extract_chat_id(payload: dict[str, Any]) -> str | None:
    raw = payload.get("chat_id")
    if raw is None and isinstance(payload.get("message"), dict):
        message = payload["message"] or {}
        raw = message.get("chat_id")
        if raw is None and isinstance(message.get("recipient"), dict):
            raw = (message.get("recipient") or {}).get("chat_id")
    if raw is None:
        return None
    normalized = str(raw).strip()
    return normalized or None


def _extract_message(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None, None
    body = message.get("body")
    if isinstance(body, dict):
        text = body.get("text")
        message_id = body.get("mid") or body.get("message_id") or body.get("id")
    else:
        text = message.get("text")
        message_id = message.get("mid") or message.get("message_id") or message.get("id")
    normalized_text = str(text).strip() if text is not None else None
    normalized_id = str(message_id).strip() if message_id is not None else None
    return normalized_text or None, normalized_id or None


def _extract_callback(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    callback = payload.get("callback")
    if not isinstance(callback, dict):
        callback = payload
    callback_id = str(
        callback.get("callback_id")
        or callback.get("id")
        or payload.get("callback_id")
        or payload.get("id")
        or ""
    ).strip() or None
    callback_payload = str(
        callback.get("payload")
        or callback.get("data")
        or callback.get("value")
        or callback.get("text")
        or payload.get("payload")
        or payload.get("data")
        or ""
    ).strip() or None
    return callback_id, callback_payload


def _truncate_callback_payload(value: str | None, *, limit: int = 96) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def _build_startapp_url(settings: Settings, *, start_param: str) -> str | None:
    base_url = str(settings.max_miniapp_url or "").strip()
    if not base_url:
        return None
    parsed = urlsplit(base_url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("startapp", start_param))
    return urlunsplit(parsed._replace(query=urlencode(query)))


async def _chat_message_exists(client_request_id: str) -> bool:
    async with async_session() as session:
        existing = await session.scalar(
            select(ChatMessage.id).where(ChatMessage.client_request_id == client_request_id)
        )
        return existing is not None


def _start_chat_callback_payload(start_param: str | None = None) -> str:
    normalized = str(start_param or "").strip()
    if not normalized:
        return "entry:start_chat"
    return f"entry:start_chat:{normalized}"


def _contextual_welcome_buttons(*, start_param: str | None = None) -> list[list[InlineButton]]:
    return [
        [
            InlineButton(
                text="Пройти в чате",
                callback_data=_start_chat_callback_payload(start_param),
                kind="callback",
            )
        ],
        [InlineButton(text="Нужно другое время", callback_data="booking:manual_time", kind="callback")],
    ]


def _contextual_welcome_text(candidate_name: str) -> str:
    return (
        f"Здравствуйте, {candidate_name}!\n\n"
        "Вас ждёт короткая анкета RecruitSmart. Её можно пройти двумя способами:\n"
        "• открыть мини-приложение через кнопку в шапке чата;\n"
        "• продолжить здесь, в чате.\n\n"
        "Сразу после анкеты можно выбрать удобные дату и время онлайн-собеседования."
    )


def _generic_welcome_text(*, invite_might_be_active: bool) -> str:
    if invite_might_be_active:
        return (
            "Здравствуйте!\n\n"
            "У вас уже есть активный шаг RecruitSmart. Откройте мини-приложение через кнопку в шапке чата "
            "или продолжите здесь, в чате. После анкеты можно будет выбрать дату и время онлайн-собеседования."
        )
    return (
        "Здравствуйте!\n\n"
        "Когда RecruitSmart откроет для вас следующий шаг, в этом чате станет доступна короткая анкета и запись "
        "на онлайн-собеседование. Если приглашение уже было, откройте системную кнопку приложения в шапке чата."
    )


def _manual_review_welcome_text() -> str:
    return (
        "Здравствуйте!\n\n"
        "Не удалось безопасно восстановить анкету автоматически. "
        "RecruitSmart проверит данные и откроет следующий шаг вручную."
    )


async def _resolve_existing_chat_principal(max_user_id: str) -> tuple[str | None, Any | None]:
    normalized = str(max_user_id or "").strip()
    if not normalized:
        return None, None
    async with async_session() as session:
        async with session.begin():
            context = await resolve_max_chat_context(session, max_user_id=normalized)
            if context is None:
                return None, None
            candidate_name = str(getattr(context.candidate, "fio", "") or "").strip() or "кандидат"
            return candidate_name, context.principal


async def _load_candidate_by_max_user_id(max_user_id: str) -> User | None:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.max_user_id == max_user_id))
        if user is not None:
            await session.refresh(user)
        return user


def _manual_request_pending(candidate: User) -> bool:
    requested_at = getattr(candidate, "manual_slot_requested_at", None)
    responded_at = getattr(candidate, "manual_slot_response_at", None)
    if requested_at is None:
        return False
    if responded_at is None:
        return True
    if responded_at.tzinfo is None:
        responded_at = responded_at.replace(tzinfo=UTC)
    if requested_at.tzinfo is None:
        requested_at = requested_at.replace(tzinfo=UTC)
    return responded_at < requested_at


async def _send_max_message(
    *,
    settings: Settings,
    max_user_id: str,
    text: str,
    buttons: list[list[InlineButton]] | None = None,
    client_request_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    adapter = await ensure_max_adapter(settings=settings)
    if adapter is None:
        logger.info("max.webhook.send_skipped_adapter_disabled")
        return

    result = await adapter.send_message(max_user_id, text, buttons=buttons)
    if not result.success:
        logger.warning(
            "max.webhook.send_failed",
            extra={"max_user_id": max_user_id, "error": result.error},
        )
        return

    await log_outbound_max_message(
        max_user_id,
        text=text,
        payload=payload,
        provider_message_id=result.message_id,
        client_request_id=client_request_id,
    )


async def _handle_bot_started(payload: dict[str, Any], *, settings: Settings) -> MaxWebhookAck:
    start_param = str(payload.get("payload") or "").strip()
    max_user_id = _extract_user_id(payload)
    if not max_user_id:
        return MaxWebhookAck(
            handled=False,
            update_type="bot_started",
            ignored_reason="missing_user",
        )

    request_seed = start_param or max_user_id
    welcome_request_id = _stable_client_request_id("welcome", request_seed)
    if await _chat_message_exists(welcome_request_id):
        return MaxWebhookAck(
            update_type="bot_started",
            duplicate=True,
        )

    candidate = None
    if start_param:
        candidate = await bind_max_to_candidate(
            start_param=start_param,
            max_user_id=max_user_id,
            username=_extract_username(payload),
            display_name=_extract_display_name(payload),
            provider_chat_id=_extract_chat_id(payload),
        )

    candidate_name = str(getattr(candidate, "fio", "") or "").strip() or None
    existing_name, existing_principal = await _resolve_existing_chat_principal(max_user_id)
    if not start_param:
        prompt = None
        guidance_text = None
        principal = existing_principal
        try:
            async with async_session() as session:
                async with session.begin():
                    if principal is None:
                        principal = await bootstrap_max_chat_principal(
                            session,
                            settings=settings,
                            max_user_id=max_user_id,
                            provider_session_id=f"max-bot-started:{max_user_id}",
                            display_name=_extract_display_name(payload),
                            username=_extract_username(payload),
                        )
                    if principal is not None:
                        prompt = await activate_max_chat_handoff(session, principal)
        except MaxLaunchError as exc:
            if exc.code == "launch_context_ambiguous":
                guidance_text = _manual_review_welcome_text()
            elif exc.code != "max_rollout_disabled":
                logger.warning(
                    "max.webhook.bot_started_global_bootstrap_failed",
                    extra={"code": exc.code, "max_user_id": max_user_id},
                )
        if prompt is not None:
            await send_max_chat_prompt(
                settings=settings,
                max_user_id=max_user_id,
                prompt=prompt,
                client_request_id=welcome_request_id,
                payload={
                    "origin_channel": "max",
                    "kind": "candidate_chat_prompt",
                    "bootstrap": "global_start",
                },
            )
            return MaxWebhookAck(update_type="bot_started")
        if guidance_text:
            await _send_max_message(
                settings=settings,
                max_user_id=max_user_id,
                text=guidance_text,
                client_request_id=welcome_request_id,
                payload={
                    "origin_channel": "max",
                    "kind": "start_manual_review",
                    "active_context": existing_principal is not None,
                },
            )
            return MaxWebhookAck(update_type="bot_started")

    if candidate_name or existing_principal is not None:
        welcome_text = _contextual_welcome_text(candidate_name or existing_name or "кандидат")
        buttons = _contextual_welcome_buttons(start_param=start_param if candidate is not None else None)
    else:
        welcome_text = _generic_welcome_text(invite_might_be_active=bool(start_param))
        buttons = []

    await _send_max_message(
        settings=settings,
        max_user_id=max_user_id,
        text=welcome_text,
        buttons=buttons,
        client_request_id=welcome_request_id,
        payload={
            "origin_channel": "max",
            "kind": "start_welcome",
            "start_param_bound": bool(candidate),
            "active_context": existing_principal is not None,
            **({"start_param": start_param} if candidate is not None else {}),
        },
    )
    return MaxWebhookAck(update_type="bot_started")


async def _capture_manual_availability(candidate: User, text: str) -> bool:
    timezone_label = str(
        getattr(candidate, "manual_slot_timezone", None)
        or "Europe/Moscow"
    ).strip()
    window_start, window_end = _parse_manual_availability_window(text, timezone_label)
    if window_start is None or window_end is None:
        return False

    async with async_session() as session:
        async with session.begin():
            db_candidate = await session.get(User, candidate.id, with_for_update=True)
            if db_candidate is None:
                return False
            await save_manual_slot_response_for_user(
                session,
                db_candidate,
                window_start=window_start,
                window_end=window_end,
                note=text,
                timezone_label=timezone_label,
            )
            await apply_candidate_status(
                db_candidate,
                CandidateStatus.WAITING_SLOT,
                session=session,
                reason="manual availability from max",
            )
            city = None
            if getattr(db_candidate, "city", None):
                city = await find_city_by_plain_name(str(db_candidate.city))
            city_id = int(city.id) if city is not None else 0
            city_name = getattr(city, "name_plain", None) or str(db_candidate.city or "Не указан")
            responsible_recruiter_id = getattr(db_candidate, "responsible_recruiter_id", None)
            candidate_external_id = str(getattr(db_candidate, "max_user_id", "") or "").strip() or None
            candidate_db_id = int(db_candidate.id)
            candidate_name = str(getattr(db_candidate, "fio", "") or "").strip() or f"Кандидат #{db_candidate.id}"

    if city_id:
        try:
            await notify_recruiters_manual_availability(
                candidate_tg_id=getattr(candidate, "telegram_id", None),
                candidate_name=candidate_name,
                city_name=city_name,
                city_id=city_id,
                availability_window=f"{window_start.isoformat()} — {window_end.isoformat()}",
                availability_note=text,
                candidate_db_id=candidate_db_id,
                responsible_recruiter_id=responsible_recruiter_id,
                source_channel="max",
                candidate_external_id=candidate_external_id,
            )
        except Exception:
            logger.exception(
                "max.webhook.manual_availability_notify_failed",
                extra={"candidate_id": candidate_db_id},
            )
    return True


async def _handle_message_created(payload: dict[str, Any], *, settings: Settings) -> MaxWebhookAck:
    max_user_id = _extract_user_id(payload)
    message_text, provider_message_id = _extract_message(payload)
    if not max_user_id:
        return MaxWebhookAck(
            handled=False,
            update_type="message_created",
            ignored_reason="missing_user",
        )

    request_id = _stable_client_request_id("message", provider_message_id or message_text or max_user_id)
    if await _chat_message_exists(request_id):
        return MaxWebhookAck(update_type="message_created", duplicate=True)

    message = await log_inbound_max_message(
        max_user_id,
        text=message_text,
        provider_message_id=provider_message_id,
        client_request_id=request_id,
        payload={"update_type": "message_created", "raw": payload},
        username=_extract_username(payload),
        display_name=_extract_display_name(payload),
    )
    if message is None:
        return MaxWebhookAck(
            handled=False,
            update_type="message_created",
            ignored_reason="candidate_not_linked",
        )

    candidate = await _load_candidate_by_max_user_id(max_user_id)
    if candidate is None:
        return MaxWebhookAck(update_type="message_created")

    if message_text and _manual_request_pending(candidate):
        if await _capture_manual_availability(candidate, message_text):
            await _send_max_message(
                settings=settings,
                max_user_id=max_user_id,
                text="Спасибо. Передал рекрутеру ваше удобное время. Он свяжется с вами для подтверждения.",
                client_request_id=_stable_client_request_id("manual-ack", provider_message_id or message.id),
                payload={"origin_channel": "max", "kind": "manual_availability_ack"},
            )
        else:
            await _send_max_message(
                settings=settings,
                max_user_id=max_user_id,
                text=(
                    "Напишите, пожалуйста, удобные дату и интервал времени на ближайшие 1–2 дня. "
                    "Например: «завтра с 14:00 до 16:00»."
                ),
                client_request_id=_stable_client_request_id("manual-reprompt", provider_message_id or message.id),
                payload={"origin_channel": "max", "kind": "manual_availability_reprompt"},
            )
        return MaxWebhookAck(update_type="message_created")

    if not message_text:
        return MaxWebhookAck(update_type="message_created")

    async with async_session() as session:
        async with session.begin():
            context = await resolve_max_chat_context(session, max_user_id=max_user_id)
            if context is None:
                prompt = None
            elif is_max_chat_active(context.journey_session):
                prompt = await process_max_chat_text_answer(
                    session,
                    context.principal,
                    text=message_text,
                )
            elif wants_max_chat_handoff(message_text):
                prompt = await activate_max_chat_handoff(session, context.principal)
            else:
                prompt = await activate_max_chat_handoff(session, context.principal)

    if prompt is not None:
        await send_max_chat_prompt(
            settings=settings,
            max_user_id=max_user_id,
            prompt=prompt,
            client_request_id=_stable_client_request_id("chat-prompt", provider_message_id or message.id),
            payload={"origin_channel": "max", "kind": "candidate_chat_prompt"},
        )
    return MaxWebhookAck(update_type="message_created")


async def _handle_message_callback(payload: dict[str, Any], *, settings: Settings) -> MaxWebhookAck:
    callback_id, callback_payload = _extract_callback(payload)
    max_user_id = _extract_user_id(payload)
    logger.info(
        "max.webhook.callback_ingress",
        extra={
            "callback_id_present": bool(callback_id),
            "callback_payload": _truncate_callback_payload(callback_payload),
            "has_max_user_id": bool(max_user_id),
            "update_keys": sorted(str(key) for key in payload.keys()),
            "callback_keys": (
                sorted(str(key) for key in (payload.get("callback") or {}).keys())
                if isinstance(payload.get("callback"), dict)
                else []
            ),
            "message_recipient_keys": (
                sorted(
                    str(key)
                    for key in ((payload.get("message") or {}).get("recipient") or {}).keys()
                )
                if isinstance((payload.get("message") or {}).get("recipient"), dict)
                else []
            ),
        },
    )
    if not callback_id:
        logger.warning(
            "max.webhook.callback_ignored",
            extra={"ignored_reason": "missing_callback_id"},
        )
        return MaxWebhookAck(
            handled=False,
            update_type="message_callback",
            ignored_reason="missing_callback_id",
        )
    if not await register_callback(callback_id):
        return MaxWebhookAck(update_type="message_callback", duplicate=True)

    adapter = await ensure_max_adapter(settings=settings)
    if adapter is not None:
        try:
            await adapter.answer_callback(
                callback_id,
                notification="Действие принято",
            )
        except Exception:
            logger.exception("max.webhook.callback_answer_failed", extra={"callback_id": callback_id})

    if not max_user_id:
        logger.warning(
            "max.webhook.callback_ignored",
            extra={
                "callback_id": callback_id,
                "callback_payload": _truncate_callback_payload(callback_payload),
                "ignored_reason": "missing_user",
            },
        )
        return MaxWebhookAck(
            update_type="message_callback",
            handled=False,
            ignored_reason="missing_user",
        )

    if str(callback_payload or "").startswith("entry:start_chat"):
        prompt = None
        guidance_text = None
        async with async_session() as session:
            async with session.begin():
                context = await resolve_max_chat_context(session, max_user_id=max_user_id)
                principal = context.principal if context is not None else None
                if principal is None:
                    raw_start_param = str(callback_payload or "").split(":", 2)
                    start_param = raw_start_param[2].strip() if len(raw_start_param) == 3 else ""
                    try:
                        principal = await bootstrap_max_chat_principal(
                            session,
                            max_user_id=max_user_id,
                            start_param=start_param,
                            settings=settings,
                            provider_session_id=f"max-start-chat:{max_user_id}:{callback_id}",
                            display_name=_extract_display_name(payload),
                            username=_extract_username(payload),
                        )
                    except MaxLaunchError as exc:
                        if exc.code == "launch_context_ambiguous":
                            guidance_text = _manual_review_welcome_text()
                        else:
                            guidance_text = (
                                "Сейчас не удалось открыть анкету автоматически. "
                                "Попробуйте ещё раз чуть позже."
                                if exc.code == "max_rollout_disabled"
                                else (
                                    "Сейчас не удалось открыть анкету в чате. "
                                    "Откройте мини-приложение через кнопку в шапке чата или попросите рекрутера помочь с доступом."
                                )
                            )
                if principal is not None:
                    prompt = await activate_max_chat_handoff(session, principal)
                elif guidance_text is None:
                    guidance_text = (
                        "Сейчас не удалось открыть анкету в чате. "
                        "Откройте мини-приложение через кнопку в шапке чата или попросите рекрутера помочь с доступом."
                    )

        if guidance_text:
            await _send_max_message(
                settings=settings,
                max_user_id=max_user_id,
                text=guidance_text,
                client_request_id=_stable_client_request_id("chat-guidance", callback_id),
                payload={"origin_channel": "max", "kind": "candidate_chat_guidance"},
            )
            return MaxWebhookAck(update_type="message_callback")

        await send_max_chat_prompt(
            settings=settings,
            max_user_id=max_user_id,
            prompt=prompt,
            client_request_id=_stable_client_request_id("chat-start", callback_id),
            payload={"origin_channel": "max", "kind": "candidate_chat_prompt"},
        )
        return MaxWebhookAck(update_type="message_callback")

    candidate = await _load_candidate_by_max_user_id(max_user_id)
    if candidate is None:
        logger.warning(
            "max.webhook.callback_ignored",
            extra={
                "callback_id": callback_id,
                "callback_payload": _truncate_callback_payload(callback_payload),
                "ignored_reason": "candidate_not_linked",
            },
        )
        return MaxWebhookAck(
            handled=False,
            update_type="message_callback",
            ignored_reason="candidate_not_linked",
        )

    if callback_payload == "booking:manual_time":
        await mark_manual_slot_requested_for_candidate(
            candidate.id,
            timezone_label=getattr(candidate, "manual_slot_timezone", None),
        )
        await _send_max_message(
            settings=settings,
            max_user_id=max_user_id,
            text=(
                "Напишите удобные дату и время на ближайшие 1–2 дня. "
                "Например: «завтра с 14:00 до 16:00»."
            ),
            client_request_id=_stable_client_request_id("manual-prompt", callback_id),
            payload={"origin_channel": "max", "kind": "manual_availability_prompt"},
        )
        return MaxWebhookAck(update_type="message_callback")

    async with async_session() as session:
        async with session.begin():
            context = await resolve_max_chat_context(session, max_user_id=max_user_id)

    if context is None:
        prompt = None
    elif str(callback_payload or "").startswith("slot:book:"):
        try:
            slot_id = int(str(callback_payload).split(":", 2)[2])
        except (IndexError, TypeError, ValueError):
            prompt = None
        else:
            prompt = await book_max_chat_slot(context.principal, slot_id=slot_id)
    else:
        async with async_session() as session:
            async with session.begin():
                prompt = await process_max_chat_callback(
                    session,
                    context.principal,
                    callback_payload=callback_payload or "",
                )

    if prompt is None:
        logger.warning(
            "max.webhook.callback_ignored",
            extra={
                "callback_id": callback_id,
                "callback_payload": _truncate_callback_payload(callback_payload),
                "ignored_reason": "unsupported_callback",
            },
        )
        return MaxWebhookAck(
            update_type="message_callback",
            handled=False,
            ignored_reason="unsupported_callback",
        )

    await send_max_chat_prompt(
        settings=settings,
        max_user_id=max_user_id,
        prompt=prompt,
        client_request_id=_stable_client_request_id("chat-callback", callback_id),
        payload={"origin_channel": "max", "kind": "candidate_chat_prompt"},
    )
    return MaxWebhookAck(update_type="message_callback")


@router.post(
    "/webhook",
    response_model=MaxWebhookAck,
    dependencies=[Depends(_verify_max_webhook_secret)],
)
async def receive_max_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MaxWebhookAck:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MAX webhook payload must be an object",
        )

    update_type = _update_type(payload)
    if update_type == "bot_started":
        return await _handle_bot_started(payload, settings=settings)
    if update_type == "message_created":
        return await _handle_message_created(payload, settings=settings)
    if update_type == "message_callback":
        return await _handle_message_callback(payload, settings=settings)
    return MaxWebhookAck(
        handled=False,
        update_type=update_type or None,
        ignored_reason="unsupported_update_type",
    )


__all__ = ["router", "receive_max_webhook"]
