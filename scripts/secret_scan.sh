#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TARGETS=(
  backend
  frontend
  scripts
  .github
  .env.example
  .env.local.example
  .env.development.example
  docker-compose.yml
  README.md
)

PATTERNS=(
  "sk-proj-[A-Za-z0-9_-]{20,}"
  "sk-[A-Za-z0-9]{32,}"
  "AIza[0-9A-Za-z_-]{35}"
  "[0-9]{8,12}:[A-Za-z0-9_-]{30,}"
)

found=0
for pattern in "${PATTERNS[@]}"; do
  if rg -n --no-heading -e "$pattern" "${TARGETS[@]}" >/tmp/recruitsmart_secret_hits.txt 2>/dev/null; then
    echo "[secret-scan] Potential secret pattern detected: $pattern"
    cat /tmp/recruitsmart_secret_hits.txt
    found=1
  fi
done

if [[ $found -ne 0 ]]; then
  echo "[secret-scan] FAILED"
  exit 1
fi

echo "[secret-scan] OK"
