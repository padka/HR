#!/usr/bin/env python3
"""Manual CLI to start Interview Script fine-tuning job in OpenAI."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import aiohttp


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _api_base_url() -> str:
    base = _env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    return base or "https://api.openai.com/v1"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
    }


async def _upload_training_file(
    *,
    session: aiohttp.ClientSession,
    api_base: str,
    api_key: str,
    dataset_path: Path,
) -> str:
    form = aiohttp.FormData()
    form.add_field("purpose", "fine-tune")
    form.add_field(
        "file",
        dataset_path.read_bytes(),
        filename=dataset_path.name,
        content_type="application/jsonl",
    )
    async with session.post(
        f"{api_base}/files",
        headers=_headers(api_key),
        data=form,
    ) as resp:
        body = await resp.text()
        if resp.status >= 400:
            raise RuntimeError(f"File upload failed: HTTP {resp.status}: {body[:2000]}")
        payload = json.loads(body)
        file_id = str(payload.get("id") or "")
        if not file_id:
            raise RuntimeError("File upload succeeded but id is missing in response")
        return file_id


async def _create_finetune_job(
    *,
    session: aiohttp.ClientSession,
    api_base: str,
    api_key: str,
    model: str,
    training_file: str,
    suffix: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "training_file": training_file,
    }
    if suffix:
        payload["suffix"] = suffix

    async with session.post(
        f"{api_base}/fine_tuning/jobs",
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json=payload,
    ) as resp:
        body = await resp.text()
        if resp.status >= 400:
            raise RuntimeError(f"Fine-tune job create failed: HTTP {resp.status}: {body[:2000]}")
        return json.loads(body)


async def _fetch_job(
    *,
    session: aiohttp.ClientSession,
    api_base: str,
    api_key: str,
    job_id: str,
) -> dict[str, Any]:
    async with session.get(
        f"{api_base}/fine_tuning/jobs/{job_id}",
        headers=_headers(api_key),
    ) as resp:
        body = await resp.text()
        if resp.status >= 400:
            raise RuntimeError(f"Fine-tune job fetch failed: HTTP {resp.status}: {body[:2000]}")
        return json.loads(body)


async def _run(args: argparse.Namespace) -> int:
    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is required", file=sys.stderr)
        return 1

    dataset_path = Path(args.dataset).expanduser().resolve()
    if not dataset_path.exists():
        print(f"Dataset file not found: {dataset_path}", file=sys.stderr)
        return 1

    model = args.model or _env("OPENAI_MODEL", "gpt-5-mini")
    api_base = _api_base_url()
    timeout = aiohttp.ClientTimeout(total=120.0)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        file_id = await _upload_training_file(
            session=session,
            api_base=api_base,
            api_key=api_key,
            dataset_path=dataset_path,
        )
        print(f"training_file_id={file_id}")

        job = await _create_finetune_job(
            session=session,
            api_base=api_base,
            api_key=api_key,
            model=model,
            training_file=file_id,
            suffix=args.suffix,
        )
        job_id = str(job.get("id") or "")
        print(f"job_id={job_id}")
        print(f"status={job.get('status')}")

        if not args.wait:
            print("next_step=monitor_job_until_succeeded")
            return 0

        poll_seconds = max(5, int(args.poll_seconds or 20))
        terminal = {"succeeded", "failed", "cancelled"}
        status = str(job.get("status") or "")
        while status not in terminal:
            await asyncio.sleep(poll_seconds)
            job = await _fetch_job(
                session=session,
                api_base=api_base,
                api_key=api_key,
                job_id=job_id,
            )
            status = str(job.get("status") or "")
            print(f"status={status}")

        if status != "succeeded":
            print(json.dumps(job, ensure_ascii=False, indent=2))
            return 2

        fine_tuned_model = str(job.get("fine_tuned_model") or "")
        print(f"fine_tuned_model={fine_tuned_model}")
        if fine_tuned_model:
            print(f"set_env=AI_INTERVIEW_SCRIPT_FT_MODEL={fine_tuned_model}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Interview Script fine-tune job in OpenAI.")
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to JSONL dataset from export_interview_script_dataset.py",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Base model for fine-tuning (default: OPENAI_MODEL)",
    )
    parser.add_argument(
        "--suffix",
        default="interview-script-v1",
        help="Optional fine-tune model suffix",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for terminal job status and print resulting model id",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=20,
        help="Polling interval when --wait is used",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())

