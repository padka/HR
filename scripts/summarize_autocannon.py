from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Row:
    name: str
    url: str
    rps_avg: float
    latency_p50_ms: float
    latency_p90_ms: float
    latency_p99_ms: float
    non2xx: int
    errors: int
    timeouts: int


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: summarize_autocannon.py <result1.json> <result2.json> ...", file=sys.stderr)
        return 2

    rows: list[Row] = []
    for fname in argv[1:]:
        path = Path(fname)
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            continue
        data = json.loads(raw)

        rows.append(
            Row(
                name=path.stem,
                url=str(data.get("url", "")),
                rps_avg=_num(data.get("requests", {}).get("average")),
                latency_p50_ms=_num(data.get("latency", {}).get("p50")),
                latency_p90_ms=_num(data.get("latency", {}).get("p90")),
                latency_p99_ms=_num(data.get("latency", {}).get("p99")),
                non2xx=int(data.get("non2xx", 0) or 0),
                errors=int(data.get("errors", 0) or 0),
                timeouts=int(data.get("timeouts", 0) or 0),
            )
        )

    if not rows:
        print("No results found.")
        return 1

    rows.sort(key=lambda r: r.name)

    total_rps = sum(r.rps_avg for r in rows)
    print(f"Total achieved RPS (sum avg): {total_rps:.0f}")
    print("")

    header = (
        "name",
        "rps_avg",
        "p50_ms",
        "p90_ms",
        "p99_ms",
        "non2xx",
        "errors",
        "timeouts",
    )
    print("{:<18} {:>9} {:>8} {:>8} {:>8} {:>8} {:>7} {:>9}".format(*header))
    print("-" * 78)
    for r in rows:
        print(
            "{:<18} {:>9.0f} {:>8.1f} {:>8.1f} {:>8.1f} {:>8} {:>7} {:>9}".format(
                r.name,
                r.rps_avg,
                r.latency_p50_ms,
                r.latency_p90_ms,
                r.latency_p99_ms,
                r.non2xx,
                r.errors,
                r.timeouts,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

