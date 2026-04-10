#!/usr/bin/env python3
"""Read-only MAX pilot cohort integrity audit."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import or_, select
from sqlalchemy.exc import OperationalError, ProgrammingError

from backend.core.db import async_session
from backend.domain.candidates.max_owner_preflight import collect_max_owner_preflight_report
from backend.domain.candidates.models import User
from backend.domain.candidates.scheduling_integrity import (
    INTEGRITY_STATE_NEEDS_MANUAL_REPAIR,
    WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR,
    load_candidate_scheduling_integrity,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit MAX pilot cohort for owner and scheduling integrity blockers.",
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
        default=100,
        help="Maximum number of MAX-linked candidates to inspect.",
    )
    parser.add_argument(
        "--candidate-id",
        dest="candidate_ids",
        action="append",
        type=int,
        default=[],
        help="Restrict the audit to one or more candidate primary keys.",
    )
    parser.add_argument(
        "--fail-on-blockers",
        action="store_true",
        help="Exit with code 2 when owner or scheduling blockers are present.",
    )
    return parser.parse_args()


def _serialize_candidate(candidate: User, scheduling_summary: dict[str, Any]) -> dict[str, Any]:
    issues = scheduling_summary.get("issues") or []
    return {
        "candidate_pk": int(candidate.id),
        "candidate_uuid": str(candidate.candidate_id or ""),
        "fio": candidate.fio,
        "messenger_platform": candidate.messenger_platform,
        "max_user_id": candidate.max_user_id,
        "status": candidate.candidate_status,
        "integrity_state": scheduling_summary.get("integrity_state"),
        "write_behavior": scheduling_summary.get("write_behavior"),
        "write_owner": scheduling_summary.get("write_owner"),
        "repairability": scheduling_summary.get("repairability"),
        "issue_codes": [
            str(item.get("code") or "").strip()
            for item in issues
            if str(item.get("code") or "").strip()
        ],
        "manual_repair_reasons": list(scheduling_summary.get("manual_repair_reasons") or []),
        "blocking": (
            scheduling_summary.get("integrity_state") == INTEGRITY_STATE_NEEDS_MANUAL_REPAIR
            or scheduling_summary.get("write_behavior") == WRITE_BEHAVIOR_NEEDS_MANUAL_REPAIR
        ),
    }


def _render_text(payload: dict[str, Any]) -> str:
    owner_ready = "yes" if payload["owner_preflight"]["ready_for_unique_index"] else "no"
    lines = [
        "MAX pilot cohort audit",
        f"- owner preflight ready: {owner_ready}",
        f"- owner blocking checks: {', '.join(payload['owner_preflight']['blocking_checks']) or 'none'}",
        f"- candidates inspected: {payload['summary']['candidates_inspected']}",
        f"- scheduling blockers: {payload['summary']['scheduling_blockers']}",
        f"- blocking candidate ids: {', '.join(str(item['candidate_pk']) for item in payload['blocking_candidates']) or 'none'}",
        "",
    ]
    for item in payload["blocking_candidates"]:
        lines.append(
            f"* #{item['candidate_pk']} {item['fio'] or 'candidate'}"
            f" | owner={item['max_user_id'] or 'none'}"
            f" | integrity={item['integrity_state']}"
            f" | write={item['write_behavior']}"
            f" | issues={', '.join(item['issue_codes']) or 'none'}"
        )
    return "\n".join(lines).strip()


async def _run(args: argparse.Namespace) -> int:
    try:
        async with async_session() as session:
            owner_report = await collect_max_owner_preflight_report(
                session,
                sample_limit=max(1, int(args.limit)),
            )

            stmt = (
                select(User)
                .where(
                    or_(
                        User.max_user_id.is_not(None),
                        User.messenger_platform == "max",
                    )
                )
                .order_by(User.id.asc())
                .limit(max(1, int(args.limit)))
            )
            if args.candidate_ids:
                stmt = stmt.where(User.id.in_(sorted(set(int(item) for item in args.candidate_ids))))

            candidates = list((await session.execute(stmt)).scalars().all())
            candidate_rows: list[dict[str, Any]] = []
            blocking_candidates: list[dict[str, Any]] = []
            for candidate in candidates:
                scheduling_summary = await load_candidate_scheduling_integrity(session, candidate)
                row = _serialize_candidate(candidate, scheduling_summary)
                candidate_rows.append(row)
                if row["blocking"]:
                    blocking_candidates.append(row)
    except (OperationalError, ProgrammingError) as exc:
        print(
            "MAX pilot cohort audit failed: database schema is unavailable or not migrated.",
            file=sys.stderr,
        )
        print(str(getattr(exc, "orig", exc)), file=sys.stderr)
        return 1

    payload = {
        "summary": {
            "candidates_inspected": len(candidate_rows),
            "scheduling_blockers": len(blocking_candidates),
            "pilot_ready": bool(owner_report.ready_for_unique_index and not blocking_candidates),
        },
        "owner_preflight": {
            "ready_for_unique_index": owner_report.ready_for_unique_index,
            "blocking_checks": list(owner_report.blocking_checks),
            "requirements_before_unique_index": list(owner_report.requirements_before_unique_index),
            "blast_radius": owner_report.blast_radius.to_dict(),
        },
        "blocking_candidates": blocking_candidates,
        "candidates": candidate_rows,
    }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_render_text(payload))

    if args.fail_on_blockers and not payload["summary"]["pilot_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run(_parse_args())))
