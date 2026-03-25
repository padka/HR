#!/usr/bin/env python3
"""Export Interview Script feedback rows into a JSONL fine-tuning dataset."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.ai.redaction import redact_text
from backend.core.db import async_session
from backend.core.settings import get_settings
from backend.domain.ai.models import AIInterviewScriptFeedback


def _mask_string(value: str) -> str:
    text = str(value or "")
    if not text:
        return text
    redacted = redact_text(
        text,
        max_len=max(2000, len(text) + 32),
        mask_person_names=True,
    )
    return redacted.text


def _mask_obj(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _mask_obj(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_obj(item) for item in value]
    if isinstance(value, str):
        return _mask_string(value)
    return value


def _is_quality_sample(row: AIInterviewScriptFeedback) -> bool:
    labels = row.labels_json if isinstance(row.labels_json, dict) else {}
    helped = labels.get("helped")
    outcome = str(labels.get("outcome") or row.outcome or "unknown")
    has_edit = bool(row.edited and isinstance(row.output_final_json, dict) and row.output_final_json)
    if not has_edit:
        return False
    if helped is True:
        return True
    return outcome in {"od_assigned", "showed_up"}


def _to_training_row(row: AIInterviewScriptFeedback) -> dict[str, Any] | None:
    input_redacted = row.input_redacted_json if isinstance(row.input_redacted_json, dict) else {}
    output_original = row.output_original_json if isinstance(row.output_original_json, dict) else {}
    output_final = row.output_final_json if isinstance(row.output_final_json, dict) else output_original
    if not output_final:
        return None

    input_masked = _mask_obj(input_redacted)
    output_masked = _mask_obj(output_final)
    output_original_masked = _mask_obj(output_original)
    labels = _mask_obj(row.labels_json if isinstance(row.labels_json, dict) else {})

    candidate_hash = hashlib.sha256(f"candidate:{int(row.candidate_id)}".encode("utf-8")).hexdigest()[:16]
    user_payload = {
        "candidate_profile": input_masked.get("candidate_profile") or {},
        "hh_resume_normalized": input_masked.get("hh_resume_normalized") or {},
        "office_context": input_masked.get("office_context") or {},
        "task": "Generate Interview Script JSON with strict schema.",
    }
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Attila Recruiting Interview Script Generator. "
                    "Return one valid JSON object. No markdown. No extra keys."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True),
            },
            {
                "role": "assistant",
                "content": json.dumps(output_masked, ensure_ascii=False, sort_keys=True),
            },
        ],
        "metadata": {
            "feedback_id": int(row.id),
            "candidate_hash": candidate_hash,
            "model": str(row.model or ""),
            "prompt_version": str(row.prompt_version or ""),
            "input_hash": str(row.input_hash or ""),
            "labels": labels,
            "output_original": output_original_masked,
        },
    }


async def _export(*, out_path: Path, min_samples: int, only_quality: bool, limit: int | None) -> tuple[int, int]:
    rows: list[AIInterviewScriptFeedback]
    async with async_session() as session:
        stmt = (
            select(AIInterviewScriptFeedback)
            .order_by(AIInterviewScriptFeedback.created_at.desc(), AIInterviewScriptFeedback.id.desc())
        )
        if limit and limit > 0:
            stmt = stmt.limit(int(limit))
        rows = list((await session.execute(stmt)).scalars().all())

    total = len(rows)
    selected = []
    for row in rows:
        if only_quality and not _is_quality_sample(row):
            continue
        sample = _to_training_row(row)
        if sample is None:
            continue
        selected.append(sample)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for item in selected:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"feedback_rows_total={total}")
    print(f"dataset_samples={len(selected)}")
    print(f"dataset_path={out_path}")
    print(f"readiness_threshold={int(min_samples)}")
    print(f"ready_for_finetune={'yes' if len(selected) >= min_samples else 'no'}")
    return total, len(selected)


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Export Interview Script dataset for fine-tuning.")
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "tmp" / "interview_script_ft_dataset.jsonl"),
        help="Output JSONL path",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=int(getattr(settings, "ai_interview_script_ft_min_samples", 300) or 300),
        help="Readiness threshold",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include non-quality feedback rows (default: only quality/gold samples)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit")
    args = parser.parse_args()

    out_path = Path(args.out).expanduser().resolve()
    min_samples = max(1, int(args.min_samples or 1))
    only_quality = not bool(args.all)
    limit = int(args.limit or 0) or None

    _, selected = asyncio.run(
        _export(
            out_path=out_path,
            min_samples=min_samples,
            only_quality=only_quality,
            limit=limit,
        )
    )
    return 0 if selected >= min_samples else 2


if __name__ == "__main__":
    raise SystemExit(main())
