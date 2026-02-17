from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CRITICAL_ROUTES = (
    "/api/profile",
    "/api/dashboard/summary",
    "/api/dashboard/incoming",
    "/api/calendar/events",
)


@dataclass(frozen=True)
class AutocannonSummary:
    achieved_rps: float
    ok_2xx: int
    non2xx: int
    errors: int
    timeouts: int


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


def _load_json(path: Path) -> dict[str, Any] | None:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    return json.loads(raw)


def _aggregate_autocannon(out_dir: Path) -> AutocannonSummary:
    ok = non2xx = errors = timeouts = 0
    achieved_rps = 0.0
    for path in out_dir.glob("*.json"):
        data = _load_json(path)
        if not data:
            continue
        achieved_rps += _num(data.get("requests", {}).get("average"))
        ok += _int(data.get("2xx", 0))
        non2xx += _int(data.get("non2xx", 0))
        errors += _int(data.get("errors", 0))
        timeouts += _int(data.get("timeouts", 0))
    return AutocannonSummary(
        achieved_rps=float(achieved_rps),
        ok_2xx=ok,
        non2xx=non2xx,
        errors=errors,
        timeouts=timeouts,
    )


_METRIC_LINE_RE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)\{([^}]*)\}\s+([0-9eE+\\-.]+)\s*$")


def _parse_labels(raw: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for part in (raw or "").split(","):
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"')
        if k:
            labels[k] = v
    return labels


def _iter_metrics_lines(path: Path) -> Iterable[tuple[str, dict[str, str], float]]:
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _METRIC_LINE_RE.match(line)
        if not m:
            continue
        name, raw_labels, raw_value = m.groups()
        labels = _parse_labels(raw_labels)
        try:
            value = float(raw_value)
        except Exception:
            continue
        yield name, labels, value


def _route_latency(metrics_path: Path) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for name, labels, value in _iter_metrics_lines(metrics_path):
        if name not in {"latency_p95_seconds", "latency_p99_seconds"}:
            continue
        route = labels.get("route")
        if not route:
            continue
        if route not in CRITICAL_ROUTES:
            continue
        if labels.get("outcome") != "success":
            continue
        if labels.get("status") != "200":
            continue
        if labels.get("method") != "GET":
            continue
        out.setdefault(route, {})
        out[route][("p95" if name.endswith("p95_seconds") else "p99")] = float(value)
    return out


def _histogram_quantile(buckets: list[tuple[float, float]], q: float) -> float | None:
    """Compute a bucket-based quantile from cumulative histogram buckets.

    Args:
        buckets: List of (le, cumulative_count) sorted by le.
        q: Quantile in [0..1].
    """

    if not buckets:
        return None
    total = buckets[-1][1]
    if total <= 0:
        return None
    target = q * total
    for le, count in buckets:
        if count >= target:
            return le
    return buckets[-1][0]


def _pool_acquire_p95(metrics_path: Path) -> dict[str, float]:
    """Return p95 pool acquire time (seconds) per route (bucket-based)."""

    by_route: dict[str, list[tuple[float, float]]] = {}
    for name, labels, value in _iter_metrics_lines(metrics_path):
        if name != "db_pool_acquire_seconds_bucket":
            continue
        route = labels.get("route")
        le_raw = labels.get("le")
        if not route or not le_raw:
            continue
        if route not in CRITICAL_ROUTES:
            continue
        if le_raw == "+Inf":
            le = float("inf")
        else:
            try:
                le = float(le_raw)
            except Exception:
                continue
        by_route.setdefault(route, []).append((le, float(value)))

    out: dict[str, float] = {}
    for route, buckets in by_route.items():
        buckets.sort(key=lambda x: x[0])
        # Drop +Inf from output quantile value when it is selected (means: beyond largest bucket).
        q = _histogram_quantile(buckets, 0.95)
        if q is None:
            continue
        out[route] = float(q)
    return out


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: analyze_step.py <out_dir> <target_total_rps>", file=sys.stderr)
        return 2

    out_dir = Path(argv[1])
    target_total = float(argv[2])
    metrics_path = out_dir / "metrics.txt"

    ac = _aggregate_autocannon(out_dir)
    attempts = max(1, ac.ok_2xx + ac.non2xx + ac.errors + ac.timeouts)
    error_rate = float(ac.non2xx + ac.errors + ac.timeouts) / float(attempts)

    latency_by_route = _route_latency(metrics_path)
    pool_p95_by_route = _pool_acquire_p95(metrics_path)

    max_p95 = max((v.get("p95", 0.0) for v in latency_by_route.values()), default=0.0)
    max_p99 = max((v.get("p99", 0.0) for v in latency_by_route.values()), default=0.0)
    max_pool_p95 = max((v for v in pool_p95_by_route.values()), default=0.0)

    # Knee thresholds (defaults aligned with the project spec).
    thr_err = _env_float("KNEE_ERROR_RATE_MAX", 0.005)
    thr_p95 = _env_float("KNEE_LATENCY_P95_MAX_SECONDS", 0.5)
    thr_p99 = _env_float("KNEE_LATENCY_P99_MAX_SECONDS", 1.5)
    thr_pool = _env_float("KNEE_POOL_ACQUIRE_P95_MAX_SECONDS", 0.05)

    reasons: list[str] = []
    if error_rate > thr_err:
        reasons.append(f"error_rate>{thr_err}")
    if max_p95 > thr_p95:
        reasons.append(f"latency_p95>{thr_p95}")
    if max_p99 > thr_p99:
        reasons.append(f"latency_p99>{thr_p99}")
    if max_pool_p95 > thr_pool:
        reasons.append(f"pool_acquire_p95>{thr_pool}")

    is_knee = bool(reasons)
    client_capped = ac.achieved_rps < (target_total * 0.9)

    payload: dict[str, Any] = {
        "target_total_rps": target_total,
        "achieved_total_rps": round(ac.achieved_rps, 2),
        "client_capped": client_capped,
        "attempts_total": attempts,
        "ok_2xx": ac.ok_2xx,
        "non2xx": ac.non2xx,
        "errors": ac.errors,
        "timeouts": ac.timeouts,
        "error_rate": round(error_rate, 6),
        "max_latency_p95_seconds": round(max_p95, 6),
        "max_latency_p99_seconds": round(max_p99, 6),
        "max_db_pool_acquire_p95_seconds": round(max_pool_p95, 6),
        "is_knee": is_knee,
        "reasons": reasons,
        "routes": latency_by_route,
        "pool_acquire_p95": pool_p95_by_route,
    }

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

