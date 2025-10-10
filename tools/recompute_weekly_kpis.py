"""Management script to recompute weekly KPI snapshots."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, timedelta
from typing import Iterable

from backend.apps.admin_ui.services.kpis import (
    compute_weekly_snapshot,
    get_week_window,
    reset_weekly_cache,
    store_weekly_snapshot,
)
from backend.core.bootstrap import ensure_database_ready


async def _recompute_range(week_starts: Iterable[date], tz_name: str | None) -> None:
    for week_start in week_starts:
        snapshot = await compute_weekly_snapshot(week_start, tz_name=tz_name)
        await store_weekly_snapshot(snapshot)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute weekly KPI snapshots")
    parser.add_argument(
        "--weeks",
        type=int,
        default=8,
        help="Количество недель для пересчёта (без учёта текущей по умолчанию)",
    )
    parser.add_argument(
        "--timezone",
        type=str,
        default=None,
        help="Таймзона компании (по умолчанию берётся из окружения)",
    )
    parser.add_argument(
        "--include-current",
        action="store_true",
        help="Добавить в пересчёт текущую неделю (по умолчанию только завершённые недели)",
    )
    parser.add_argument(
        "--week",
        type=str,
        default=None,
        help="Пересчитать только указанную неделю (формат YYYY-MM-DD)",
    )

    args = parser.parse_args()

    await ensure_database_ready()

    tz_name = args.timezone

    if args.week:
        try:
            week_start = date.fromisoformat(args.week)
        except ValueError as exc:  # pragma: no cover - defensive
            raise SystemExit(f"Некорректная дата недели: {args.week}") from exc
        await _recompute_range([week_start], tz_name)
    else:
        window = get_week_window(tz_name=tz_name)
        base_start = window.week_start_date
        total_weeks = max(0, args.weeks)
        offsets = range(0 if args.include_current else 1, total_weeks + (1 if not args.include_current else 0))
        week_starts = [base_start - timedelta(weeks=offset) for offset in offsets]
        await _recompute_range(week_starts, tz_name)

    await reset_weekly_cache()


if __name__ == "__main__":
    asyncio.run(main())
