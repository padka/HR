# Scenario Simulator Runbook (Local Only)

## Purpose

Локальный `Scenario Simulator` прогоняет эталонные воронки без вмешательства в прод:

- `happy_path`
- `reschedule_loop`
- `decline_path`
- `intro_day_missing_feedback`

## Feature flags

Backend:

- `SIMULATOR_ENABLED=true`

Frontend (опционально, чтобы пункт был в навигации):

- `VITE_SIMULATOR_ENABLED=true`

## API

- `POST /api/simulator/runs`
- `GET /api/simulator/runs/{run_id}`
- `GET /api/simulator/runs/{run_id}/report`

## UI

- `/app/simulator` (только `admin`)

## Acceptance checks

1. Запустить сценарий через UI/POST API.
2. Получить `run_id`.
3. Проверить отчет `/report`:
   - `total_steps`, `successful_steps`, `failed_steps`
   - `total_duration_ms`
   - `bottlenecks`
4. Проверить, что `intro_day_missing_feedback` завершается со статусом `failed`.

## Safety

- Используется только локально, прод не затрагивается.
- Эндпоинты скрыты при `SIMULATOR_ENABLED=false`.
