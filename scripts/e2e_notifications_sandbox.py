#!/usr/bin/env python
"""
Run an end-to-end notification exercise against a lightweight Telegram sandbox.

The script:
1. Spins up a local HTTP server that mimics Telegram Bot API endpoints.
2. Configures the bot + notification service to talk to that sandbox.
3. Seeds the database with demo recruiter/candidate/slot/template data.
4. Enqueues candidate & recruiter notifications and forces a poll cycle.
5. Verifies that NotificationLog records were written with delivery_status="sent".

Usage:
    PYTHONPATH=. python scripts/e2e_notifications_sandbox.py \
        --candidate-chat-id 90001 \
        --recruiter-chat-id 90002
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from aiohttp import web
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from sqlalchemy import select

from backend.apps.bot.services import (
    NotificationService,
    configure,
    configure_notification_service,
)
from backend.apps.bot.state_store import InMemoryStateStore, StateManager
from backend.core.db import async_session
from backend.domain import models
from backend.domain.models import MessageTemplate, NotificationLog, SlotStatus
from backend.domain.repositories import add_outbox_notification

logger = logging.getLogger("sandbox")

SANDBOX_TEMPLATE_CANDIDATE = "Ваш статус обновлён: {status} по брони #{booking_id}."
SANDBOX_TEMPLATE_RECRUITER = (
    "Кандидат {candidate_name} подтвердил слот на {dt_local} ({tz_name}). Ссылка: {join_link}"
)


class TelegramSandbox:
    """Minimal HTTP server that emulates Telegram Bot API endpoints."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._app = web.Application()
        self._app.router.add_post("/{tail:.*}", self._handle_request)
        self.requests: List[Dict[str, object]] = []

    @property
    def base_url(self) -> str:
        assert self._site is not None
        sock = self._site._server.sockets[0]  # type: ignore[attr-defined]
        host, port = sock.getsockname()[:2]
        return f"http://{host}:{port}"

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        logger.info("Telegram sandbox listening on %s", self.base_url)

    async def close(self) -> None:
        if self._site is not None:
            await self._site.stop()
        if self._runner is not None:
            await self._runner.cleanup()

    async def _handle_request(self, request: web.Request) -> web.StreamResponse:
        method = request.path.rsplit("/", 1)[-1]
        if request.content_type == "application/json":
            payload = await request.json()
        else:
            form = await request.post()
            payload = dict(form)
        entry = {"method": method, "payload": payload}
        self.requests.append(entry)
        logger.debug("Sandbox received %s: %s", method, payload)
        response = {
            "ok": True,
            "result": {
                "message_id": len(self.requests),
                "date": int(datetime.now(timezone.utc).timestamp()),
            },
        }
        return web.json_response(response)


async def ensure_templates(session, now: datetime) -> None:
    """Create or refresh sandbox templates required for the flow."""

    async def _upsert(key: str, body: str) -> None:
        template = await session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.key == key,
                MessageTemplate.locale == "ru",
                MessageTemplate.channel == "tg",
            )
        )
        if template is None:
            template = MessageTemplate(
                key=key,
                locale="ru",
                channel="tg",
                body_md=body,
                version=1,
                is_active=True,
                updated_at=now,
            )
            session.add(template)
        else:
            template.body_md = body
            template.is_active = True
            template.updated_at = now

    await _upsert("candidate_rejection", SANDBOX_TEMPLATE_CANDIDATE)
    await _upsert("recruiter_candidate_confirmed_notice", SANDBOX_TEMPLATE_RECRUITER)


async def seed_demo_entities(candidate_chat_id: int, recruiter_chat_id: int) -> Tuple[int, int]:
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        async with session.begin():
            await ensure_templates(session, now)

            city = models.City(name="Sandbox City", tz="Europe/Moscow", active=True)
            recruiter = models.Recruiter(
                name="Sandbox Recruiter",
                tz="Europe/Moscow",
                telemost_url="https://t.me/joinchat/sandbox",
                active=True,
                tg_chat_id=recruiter_chat_id,
            )
            recruiter.cities.append(city)
            session.add_all([city, recruiter])

            slot = models.Slot(
                recruiter=recruiter,
                city=city,
                start_utc=now + timedelta(hours=2),
                status=SlotStatus.BOOKED,
                candidate_tg_id=candidate_chat_id,
                candidate_fio="Sandbox Candidate",
                candidate_city_id=city.id,
                candidate_tz=city.tz,
            )
            session.add(slot)

        await session.refresh(slot)
        await session.refresh(recruiter)
        return slot.id, slot.candidate_tg_id


async def enqueue_notifications(slot_id: int, candidate_tg_id: int) -> None:
    await add_outbox_notification(
        notification_type="candidate_rejection",
        booking_id=slot_id,
        candidate_tg_id=candidate_tg_id,
    )
    await add_outbox_notification(
        notification_type="recruiter_candidate_confirmed_notice",
        booking_id=slot_id,
        candidate_tg_id=candidate_tg_id,
    )


async def fetch_logs(slot_id: int) -> List[NotificationLog]:
    async with async_session() as session:
        rows = (
            await session.execute(
                select(NotificationLog)
                .where(NotificationLog.booking_id == slot_id)
                .order_by(NotificationLog.id.asc())
            )
        ).scalars()
        return list(rows)


async def run_sandbox_flow(args) -> Dict[str, object]:
    sandbox = TelegramSandbox(args.sandbox_host, args.sandbox_port)
    await sandbox.start()

    api = TelegramAPIServer.from_base(sandbox.base_url)
    session = AiohttpSession(api=api)
    bot = Bot(token=args.bot_token, session=session)

    store = InMemoryStateStore(ttl_seconds=3600)
    state_manager = StateManager(store)
    configure(bot, state_manager)

    service = NotificationService(
        poll_interval=0.25,
        batch_size=10,
        rate_limit_per_sec=50,
        worker_concurrency=1,
    )
    configure_notification_service(service)

    logs: List[NotificationLog] = []
    sent_types: List[str] = []
    slot_id: Optional[int] = None

    try:
        slot_id, candidate_tg_id = await seed_demo_entities(
            args.candidate_chat_id, args.recruiter_chat_id
        )
        await enqueue_notifications(slot_id, candidate_tg_id or args.candidate_chat_id)

        await service._poll_once()  # noqa: SLF001 - internal usage for diagnostics only

        logs = await fetch_logs(slot_id)
        sent_types = sorted({log.type for log in logs if log.delivery_status == "sent"})
    finally:
        await service.shutdown()
        await state_manager.clear()
        await store.close()
        await bot.session.close()
        await sandbox.close()

    return {
        "slot_id": slot_id,
        "log_count": len(logs),
        "sent_types": sent_types,
        "sandbox_requests": sandbox.requests,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run notification E2E flow against Telegram sandbox"
    )
    parser.add_argument("--bot-token", default="sandbox:test", help="Bot token used for sandbox requests")
    parser.add_argument("--candidate-chat-id", type=int, default=990001)
    parser.add_argument("--recruiter-chat-id", type=int, default=990002)
    parser.add_argument("--sandbox-host", default="127.0.0.1")
    parser.add_argument("--sandbox-port", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args()
    try:
        summary = asyncio.run(run_sandbox_flow(args))
    except KeyboardInterrupt:
        return 130

    print(json.dumps(summary, indent=2))
    required = {"candidate_rejection", "recruiter_candidate_confirmed_notice"}
    return 0 if required.issubset(set(summary.get("sent_types", []))) else 1


if __name__ == "__main__":
    raise SystemExit(main())
