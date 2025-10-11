#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root_dir"

echo "==> Codex :: install dependencies"
make install

echo "==> Codex :: run pre-commit"
pre-commit run --all-files --show-diff-on-failure

echo "==> Codex :: execute test suite"
make test

echo "==> Codex :: build UI"
make ui
