from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from backend.apps.admin_ui.security import Principal, require_admin, require_csrf_token
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.simulator.models import SimulatorRun, SimulatorStep

router = APIRouter(prefix="/api/simulator", tags=["simulator"])
admin_dep = Depends(require_admin)

SIMULATOR_SCENARIOS: dict[str, list[dict[str, Any]]] = {
    "happy_path": [
        {"key": "candidate_created", "title": "Создан кандидат", "duration_ms": 1100},
        {"key": "test1_completed", "title": "Пройден тест 1", "duration_ms": 1500},
        {"key": "slot_offered", "title": "Предложен слот", "duration_ms": 1700},
        {"key": "slot_confirmed", "title": "Слот подтвержден", "duration_ms": 1800},
        {"key": "intro_day_scheduled", "title": "Назначен ознакомительный день", "duration_ms": 1300},
    ],
    "reschedule_loop": [
        {"key": "slot_offered_1", "title": "Первый слот предложен", "duration_ms": 1200},
        {"key": "candidate_requests_reschedule", "title": "Кандидат просит перенос", "duration_ms": 2400},
        {"key": "slot_offered_2", "title": "Предложен альтернативный слот", "duration_ms": 1500},
        {"key": "slot_confirmed", "title": "Новый слот подтвержден", "duration_ms": 1700},
    ],
    "decline_path": [
        {"key": "test1_completed", "title": "Пройден тест 1", "duration_ms": 900},
        {"key": "slot_offered", "title": "Предложен слот", "duration_ms": 1600},
        {"key": "candidate_declined", "title": "Кандидат отказался", "duration_ms": 2100},
        {"key": "rejection_sent", "title": "Отправлено уведомление об отказе", "duration_ms": 900},
    ],
    "intro_day_missing_feedback": [
        {"key": "slot_confirmed", "title": "Слот подтвержден", "duration_ms": 1000},
        {"key": "intro_day_done", "title": "Ознакомительный день завершен", "duration_ms": 2800},
        {
            "key": "office_feedback_timeout",
            "title": "Нет обратной связи от офиса в SLA",
            "duration_ms": 3500,
            "status": "failed",
            "details": {"reason": "missing_feedback", "sla_hours": 24},
        },
    ],
}


def _ensure_enabled() -> None:
    if not get_settings().simulator_enabled:
        raise HTTPException(status_code=404, detail={"message": "Simulator disabled"})


def _serialize_step(step: SimulatorStep) -> dict[str, Any]:
    return {
        "id": int(step.id),
        "step_order": int(step.step_order),
        "step_key": step.step_key,
        "title": step.title,
        "status": step.status,
        "started_at": step.started_at.astimezone(UTC).isoformat() if step.started_at else None,
        "finished_at": step.finished_at.astimezone(UTC).isoformat() if step.finished_at else None,
        "duration_ms": int(step.duration_ms or 0),
        "details": step.details_json or {},
    }


def _serialize_run(run: SimulatorRun, *, include_steps: bool = False) -> dict[str, Any]:
    payload = {
        "id": int(run.id),
        "scenario": run.scenario,
        "status": run.status,
        "started_at": run.started_at.astimezone(UTC).isoformat() if run.started_at else None,
        "finished_at": run.finished_at.astimezone(UTC).isoformat() if run.finished_at else None,
        "summary": run.summary_json or {},
    }
    if include_steps:
        payload["steps"] = [_serialize_step(step) for step in sorted(run.steps, key=lambda s: s.step_order)]
    return payload


@router.post("/runs")
async def simulator_create_run(
    request: Request,
    principal: Principal = admin_dep,
) -> JSONResponse:
    _ensure_enabled()
    _ = await require_csrf_token(request)

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"message": "Ожидался JSON"})

    scenario = str(body.get("scenario") or "happy_path").strip().lower()
    if scenario not in SIMULATOR_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail={"message": "Некорректный сценарий", "allowed": sorted(SIMULATOR_SCENARIOS.keys())},
        )

    started_at = datetime.now(UTC)
    steps_template = SIMULATOR_SCENARIOS[scenario]

    async with async_session() as session:
        run = SimulatorRun(
            scenario=scenario,
            status="running",
            started_at=started_at,
            created_by_type=principal.type,
            created_by_id=principal.id,
            summary_json={},
        )
        session.add(run)
        await session.flush()

        elapsed_ms = 0
        failed_steps = 0
        total_duration_ms = 0

        for idx, template in enumerate(steps_template, start=1):
            duration_ms = int(template.get("duration_ms") or 0)
            total_duration_ms += duration_ms
            status_value = str(template.get("status") or "success")
            step_started = started_at + timedelta(milliseconds=elapsed_ms)
            elapsed_ms += duration_ms
            step_finished = started_at + timedelta(milliseconds=elapsed_ms)
            if status_value != "success":
                failed_steps += 1
            session.add(
                SimulatorStep(
                    run_id=int(run.id),
                    step_order=idx,
                    step_key=str(template.get("key") or f"step_{idx}"),
                    title=str(template.get("title") or f"Step {idx}"),
                    status=status_value,
                    started_at=step_started,
                    finished_at=step_finished,
                    duration_ms=duration_ms,
                    details_json=dict(template.get("details") or {}),
                )
            )

        run.finished_at = started_at + timedelta(milliseconds=elapsed_ms)
        run.status = "failed" if failed_steps else "completed"
        run.summary_json = {
            "total_steps": len(steps_template),
            "successful_steps": len(steps_template) - failed_steps,
            "failed_steps": failed_steps,
            "total_duration_ms": total_duration_ms,
            "final_status": run.status,
            "bottlenecks": [
                {
                    "step_key": str(step.get("key") or ""),
                    "title": str(step.get("title") or ""),
                    "duration_ms": int(step.get("duration_ms") or 0),
                }
                for step in sorted(steps_template, key=lambda it: int(it.get("duration_ms") or 0), reverse=True)[:2]
            ],
        }

        await session.commit()
        await session.refresh(run)

    async with async_session() as session:
        run_row = await session.scalar(select(SimulatorRun).where(SimulatorRun.id == run.id))
        if run_row is None:
            raise HTTPException(status_code=500, detail={"message": "Simulator run not found"})
        steps = (
            await session.execute(
                select(SimulatorStep)
                .where(SimulatorStep.run_id == run_row.id)
                .order_by(SimulatorStep.step_order.asc())
            )
        ).scalars().all()
        payload = _serialize_run(run_row, include_steps=False)
        payload["steps"] = [_serialize_step(step) for step in steps]
        return JSONResponse({"ok": True, "run": payload}, status_code=201)


@router.get("/runs/{run_id}")
async def simulator_get_run(
    run_id: int,
    _principal: Principal = admin_dep,
) -> JSONResponse:
    _ensure_enabled()
    async with async_session() as session:
        run = await session.scalar(select(SimulatorRun).where(SimulatorRun.id == run_id))
        if run is None:
            raise HTTPException(status_code=404, detail={"message": "Run not found"})
        steps = (
            await session.execute(
                select(SimulatorStep)
                .where(SimulatorStep.run_id == run.id)
                .order_by(SimulatorStep.step_order.asc())
            )
        ).scalars().all()
        payload = _serialize_run(run, include_steps=False)
        payload["steps"] = [_serialize_step(step) for step in steps]
        return JSONResponse({"ok": True, "run": payload})


@router.get("/runs/{run_id}/report")
async def simulator_get_report(
    run_id: int,
    _principal: Principal = admin_dep,
) -> JSONResponse:
    _ensure_enabled()
    async with async_session() as session:
        run = await session.scalar(select(SimulatorRun).where(SimulatorRun.id == run_id))
        if run is None:
            raise HTTPException(status_code=404, detail={"message": "Run not found"})
        steps = (
            await session.execute(
                select(SimulatorStep)
                .where(SimulatorStep.run_id == run.id)
                .order_by(SimulatorStep.step_order.asc())
            )
        ).scalars().all()
        report = {
            "run": _serialize_run(run, include_steps=False),
            "summary": run.summary_json or {},
            "steps": [_serialize_step(step) for step in steps],
        }
        return JSONResponse({"ok": True, "report": report})
