#!/usr/bin/env python3
"""Read-only MAX duplicate-owner preflight audit."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.db import async_session
from backend.domain.candidates.max_owner_preflight import (
    collect_max_owner_preflight_report,
    render_max_owner_preflight_text,
)
from sqlalchemy.exc import OperationalError, ProgrammingError


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit MAX owner duplicates, whitespace anomalies, and cleanup readiness.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of duplicate/anomaly samples to include per section.",
    )
    parser.add_argument(
        "--fail-on-blockers",
        action="store_true",
        help="Exit with code 2 when the dataset is not ready for a unique MAX owner index.",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    try:
        async with async_session() as session:
            report = await collect_max_owner_preflight_report(
                session,
                sample_limit=max(1, int(args.limit)),
            )
    except (OperationalError, ProgrammingError) as exc:
        print(
            "MAX owner preflight failed: database schema is unavailable or not migrated. "
            "Point DATABASE_URL to an initialized RecruitSmart database before running this audit.",
            file=sys.stderr,
        )
        print(str(getattr(exc, "orig", exc)), file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_max_owner_preflight_text(report))

    if args.fail_on_blockers and not report.ready_for_unique_index:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run(_parse_args())))
