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
    ok_2xx: int
    non2xx: int
    errors: int
    timeouts: int
    requests_total: int


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _load(path: Path) -> dict[str, Any] | None:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    return json.loads(raw)


def _error_rate(row: Row) -> float:
    denom = max(1, row.ok_2xx + row.non2xx + row.errors + row.timeouts)
    return float(row.non2xx + row.errors + row.timeouts) / float(denom)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: summarize_profile.py <out_dir>", file=sys.stderr)
        return 2

    out_dir = Path(argv[1])
    paths = sorted(out_dir.glob("*.json"))
    if not paths:
        print(f"No autocannon JSON files found in: {out_dir}", file=sys.stderr)
        return 1

    rows: list[Row] = []
    for path in paths:
        data = _load(path)
        if not data:
            continue
        rows.append(
            Row(
                name=path.stem,
                url=str(data.get("url", "")),
                rps_avg=_num(data.get("requests", {}).get("average")),
                latency_p50_ms=_num(data.get("latency", {}).get("p50")),
                latency_p90_ms=_num(data.get("latency", {}).get("p90")),
                latency_p99_ms=_num(data.get("latency", {}).get("p99")),
                ok_2xx=_int(data.get("2xx", 0)),
                non2xx=_int(data.get("non2xx", 0)),
                errors=_int(data.get("errors", 0)),
                timeouts=_int(data.get("timeouts", 0)),
                requests_total=_int(data.get("requests", {}).get("total")),
            )
        )

    rows.sort(key=lambda r: r.name)
    total_rps = sum(r.rps_avg for r in rows)
    total_ok = sum(r.ok_2xx for r in rows)
    total_non2xx = sum(r.non2xx for r in rows)
    total_errors = sum(r.errors for r in rows)
    total_timeouts = sum(r.timeouts for r in rows)
    total_attempts = total_ok + total_non2xx + total_errors + total_timeouts
    total_error_rate = float(total_non2xx + total_errors + total_timeouts) / float(max(1, total_attempts))

    print(f"Total achieved RPS (sum avg): {total_rps:.0f}")
    print(
        "Total attempts: {} | ok_2xx={} non2xx={} errors={} timeouts={} | error_rate={:.2%}".format(
            total_attempts,
            total_ok,
            total_non2xx,
            total_errors,
            total_timeouts,
            total_error_rate,
        )
    )
    print("")

    header = (
        "name",
        "rps_avg",
        "p50_ms",
        "p90_ms",
        "p99_ms",
        "ok_2xx",
        "non2xx",
        "errors",
        "timeouts",
        "err_rate",
    )
    print("{:<22} {:>9} {:>8} {:>8} {:>8} {:>8} {:>7} {:>7} {:>9} {:>8}".format(*header))
    print("-" * 110)
    for r in rows:
        print(
            "{:<22} {:>9.0f} {:>8.1f} {:>8.1f} {:>8.1f} {:>8} {:>7} {:>7} {:>9} {:>7.2%}".format(
                r.name,
                r.rps_avg,
                r.latency_p50_ms,
                r.latency_p90_ms,
                r.latency_p99_ms,
                r.ok_2xx,
                r.non2xx,
                r.errors,
                r.timeouts,
                _error_rate(r),
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

