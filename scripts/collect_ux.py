#!/usr/bin/env python3
"""Collect UX telemetry logs from previews/ux_logs into summary reports."""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

LOG_DIR = Path("previews/ux_logs")
CSV_REPORT = LOG_DIR / "summary.csv"
MD_REPORT = LOG_DIR / "summary.md"


@dataclass
class Event:
    ts: Optional[datetime]
    type: str
    payload: Dict[str, Any]
    raw: Dict[str, Any]
    source: Path

    @property
    def page(self) -> Optional[str]:
        url = self.raw.get("url")
        return url if isinstance(url, str) else None


@dataclass
class Session:
    path: Path
    generated_at: Optional[datetime]
    events: List[Event]

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def first_ts(self) -> Optional[datetime]:
        for event in sorted(self.events, key=lambda e: (e.ts or datetime.max)):
            if event.ts:
                return event.ts
        return None

    @property
    def last_ts(self) -> Optional[datetime]:
        for event in sorted(self.events, key=lambda e: (e.ts or datetime.min), reverse=True):
            if event.ts:
                return event.ts
        return None


def parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    sanitized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(sanitized)
    except ValueError:
        return None


def load_events(path: Path) -> Session:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Unable to read log {path}: {exc}") from exc

    entries = data.get("entries")
    if not isinstance(entries, list):
        entries = []

    events: List[Event] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        event_type = str(entry.get("type") or "unknown")
        ts = parse_iso(entry.get("ts"))
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        events.append(Event(ts=ts, type=event_type, payload=payload, raw=entry, source=path))

    generated_at = parse_iso(data.get("generatedAt"))
    return Session(path=path, generated_at=generated_at, events=events)


def iter_log_files(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"))


def summarise_sessions(sessions: Iterable[Session]):
    sessions = list(sessions)
    if not sessions:
        return {
            "sessions": [],
            "event_counts": Counter(),
            "page_counts": Counter(),
            "element_counts": defaultdict(Counter),
        }

    event_counts: Counter = Counter()
    page_counts: Counter = Counter()
    element_counts: Dict[str, Counter] = defaultdict(Counter)

    for session in sessions:
        for event in session.events:
            event_counts[event.type] += 1
            if event.page:
                page_counts[event.page] += 1
            element = extract_element_label(event)
            if element:
                element_counts[event.type][element] += 1

    return {
        "sessions": sessions,
        "event_counts": event_counts,
        "page_counts": page_counts,
        "element_counts": element_counts,
    }


def extract_element_label(event: Event) -> Optional[str]:
    element = event.payload.get("element")
    if not isinstance(element, dict):
        return None

    identifier = element.get("label") or element.get("id") or element.get("name")
    if identifier:
        identifier = str(identifier).strip()
    else:
        identifier = element.get("tag")
        if isinstance(identifier, str):
            identifier = f"<{identifier}>"

    if not identifier:
        return None

    dataset = element.get("dataset")
    suffix = None
    if isinstance(dataset, dict):
        label_key = dataset.get("uxLabel") or dataset.get("track")
        if label_key:
            suffix = str(label_key)
    if suffix:
        identifier = f"{identifier} ({suffix})"

    return identifier


def write_csv_report(sessions: Iterable[Session], event_counts: Counter) -> None:
    sessions = list(sessions)
    CSV_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_REPORT.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = [
            "session",
            "events",
            "click",
            "filter",
            "search",
            "scroll",
            "first_ts",
            "last_ts",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for session in sessions:
            counts = Counter(event.type for event in session.events)
            writer.writerow(
                {
                    "session": session.name,
                    "events": sum(counts.values()),
                    "click": counts.get("click", 0),
                    "filter": counts.get("filter", 0),
                    "search": counts.get("search", 0),
                    "scroll": counts.get("scroll", 0),
                    "first_ts": format_dt(session.first_ts),
                    "last_ts": format_dt(session.last_ts),
                }
            )

        total_row = {
            "session": "TOTAL",
            "events": sum(event_counts.values()),
            "click": event_counts.get("click", 0),
            "filter": event_counts.get("filter", 0),
            "search": event_counts.get("search", 0),
            "scroll": event_counts.get("scroll", 0),
            "first_ts": "",
            "last_ts": "",
        }
        writer.writerow(total_row)


def format_dt(value: Optional[datetime]) -> str:
    if not value:
        return ""
    return value.isoformat()


def write_markdown_report(summary: Dict[str, Any]) -> None:
    sessions: List[Session] = summary["sessions"]
    event_counts: Counter = summary["event_counts"]
    page_counts: Counter = summary["page_counts"]
    element_counts: Dict[str, Counter] = summary["element_counts"]

    MD_REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# UX Telemetry Summary")
    lines.append("")
    lines.append(f"- Sessions processed: {len(sessions)}")
    lines.append(f"- Total events: {sum(event_counts.values())}")
    lines.append("")

    if event_counts:
        lines.append("## Events by type")
        lines.append("| Event | Count |")
        lines.append("|-------|-------|")
        for event_type, count in event_counts.most_common():
            lines.append(f"| {event_type} | {count} |")
        lines.append("")

    if sessions:
        lines.append("## Sessions")
        lines.append("| Session | Events | First event | Last event |")
        lines.append("|---------|--------|-------------|------------|")
        for session in sessions:
            lines.append(
                "| {name} | {events} | {first} | {last} |".format(
                    name=session.name,
                    events=len(session.events),
                    first=format_dt(session.first_ts) or "—",
                    last=format_dt(session.last_ts) or "—",
                )
            )
        lines.append("")

    if page_counts:
        lines.append("## Interactions by page")
        lines.append("| Page | Events |")
        lines.append("|------|--------|")
        for page, count in page_counts.most_common():
            lines.append(f"| {page} | {count} |")
        lines.append("")

    if element_counts:
        lines.append("## Top interactive elements")
        for event_type, counter in element_counts.items():
            if not counter:
                continue
            lines.append(f"### {event_type}")
            lines.append("| Element | Count |")
            lines.append("|---------|-------|")
            for element, count in counter.most_common(5):
                lines.append(f"| {element} | {count} |")
            lines.append("")

    MD_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    log_files = list(iter_log_files(LOG_DIR))
    if not log_files:
        print("No UX logs found in", LOG_DIR)
        return 0

    sessions = []
    for path in log_files:
        try:
            sessions.append(load_events(path))
        except RuntimeError as exc:
            print(exc, file=sys.stderr)

    summary = summarise_sessions(sessions)
    write_csv_report(summary["sessions"], summary["event_counts"])
    write_markdown_report(summary)

    print(f"Processed {len(summary['sessions'])} session(s)")
    print(f"Total events: {sum(summary['event_counts'].values())}")
    print(f"Reports saved to {CSV_REPORT} and {MD_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
