#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/.local/quality_snapshot"
OUT_FILE="$OUT_DIR/latest.json"
TMP_DIR="$OUT_DIR/.tmp"
FRONT_DIR="$ROOT_DIR/frontend/app"

MODE="quick"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"

if [[ "${1:-}" == "--full" ]]; then
  MODE="full"
fi

mkdir -p "$OUT_DIR" "$TMP_DIR"

timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

backend_tests_status="skipped"
backend_tests_summary=""
lint_status="skipped"
lint_warnings="null"
lint_errors="null"
typecheck_status="skipped"
unit_status="skipped"

if [[ "$MODE" == "full" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    set +e
    "$ROOT_DIR/.venv/bin/python" -m pytest -q > "$TMP_DIR/pytest.log" 2>&1
    rc=$?
    set -e
    if [[ $rc -eq 0 ]]; then
      backend_tests_status="passed"
    else
      backend_tests_status="failed"
    fi
    backend_tests_summary="$(tail -n 2 "$TMP_DIR/pytest.log" | tr '\n' ' ' | sed 's/"/\\"/g')"
  else
    backend_tests_status="unavailable"
  fi

  if [[ -f "$FRONT_DIR/package.json" ]]; then
    pushd "$FRONT_DIR" >/dev/null

    set +e
    npm run lint -- --format json > "$TMP_DIR/eslint.json" 2>/dev/null
    lint_rc=$?
    set -e
    if [[ $lint_rc -eq 0 ]]; then
      lint_status="passed"
    else
      lint_status="failed"
    fi

    if [[ -s "$TMP_DIR/eslint.json" ]]; then
      lint_warnings=$(node -e '
const fs=require("fs");
const p=process.argv[1];
try {
  const d=JSON.parse(fs.readFileSync(p,"utf8"));
  let w=0,e=0;
  for (const f of d) { w += Number(f.warningCount||0); e += Number(f.errorCount||0); }
  process.stdout.write(String(w));
  process.stderr.write(String(e));
} catch { process.stdout.write("0"); process.stderr.write("0"); }
' "$TMP_DIR/eslint.json" 2> "$TMP_DIR/eslint_err_count.txt")
      lint_errors=$(cat "$TMP_DIR/eslint_err_count.txt" || echo 0)
    else
      lint_warnings="0"
      lint_errors="0"
    fi

    set +e
    npm run typecheck > "$TMP_DIR/typecheck.log" 2>&1
    tc_rc=$?
    set -e
    if [[ $tc_rc -eq 0 ]]; then
      typecheck_status="passed"
    else
      typecheck_status="failed"
    fi

    set +e
    npm run test -- --runInBand > "$TMP_DIR/frontend-test.log" 2>&1
    ut_rc=$?
    set -e
    if [[ $ut_rc -eq 0 ]]; then
      unit_status="passed"
    else
      unit_status="failed"
    fi

    popd >/dev/null
  fi
fi

bundle_size_kb="null"
if [[ -d "$FRONT_DIR/dist" ]]; then
  bundle_size_kb=$(du -sk "$FRONT_DIR/dist" | awk '{print $1}')
fi

measure_p95() {
  local endpoint="$1"
  local file="$TMP_DIR/latency_$(echo "$endpoint" | tr '/:' '__').txt"
  : > "$file"
  for _ in {1..20}; do
    t=$(curl -s -o /dev/null -w '%{time_total}' "$API_BASE$endpoint" || echo "")
    [[ -n "$t" ]] && echo "$t" >> "$file"
  done
  local count
  count=$(wc -l < "$file" | tr -d ' ')
  if [[ "$count" -lt 5 ]]; then
    echo "null"
    return
  fi
  local idx
  idx=$(( (95 * count + 99) / 100 ))
  if [[ "$idx" -lt 1 ]]; then idx=1; fi
  sort -n "$file" | sed -n "${idx}p"
}

p95_health="$(measure_p95 "/health")"
p95_api_health="$(measure_p95 "/api/health")"

cat > "$OUT_FILE" <<JSON
{
  "generated_at": "$timestamp",
  "mode": "$MODE",
  "backend": {
    "tests_status": "$backend_tests_status",
    "tests_summary": "$backend_tests_summary"
  },
  "frontend": {
    "lint_status": "$lint_status",
    "lint_warnings": $lint_warnings,
    "lint_errors": $lint_errors,
    "typecheck_status": "$typecheck_status",
    "unit_status": "$unit_status",
    "bundle_size_kb": $bundle_size_kb
  },
  "api": {
    "base_url": "$API_BASE",
    "p95_health_sec": $p95_health,
    "p95_api_health_sec": $p95_api_health
  }
}
JSON

echo "Saved quality snapshot: $OUT_FILE"
