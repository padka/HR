#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
SYSTEM="$ROOT/.codex/system.md"

if [[ ! -s "$SYSTEM" ]]; then
  echo "Missing system prompt at $SYSTEM"; exit 1
fi

# Попробуй предпочитаемый флаг; при отсутствии — альтернативы.
if codex chat --help 2>/dev/null | grep -q -- '--system'; then
  exec codex chat --project "$ROOT" --system "$SYSTEM" "$@"
elif codex chat --help 2>/dev/null | grep -q -- '--stdin-system'; then
  exec bash -lc "cat \"$SYSTEM\" | codex chat --project \"$ROOT\" --stdin-system \"$@\""
else
  export CODEX_SYSTEM_FILE="$SYSTEM"
  exec codex chat --project "$ROOT" "$@"
fi
