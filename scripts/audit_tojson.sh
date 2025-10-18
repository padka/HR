#!/usr/bin/env bash
set -euo pipefail
echo "Searching |tojson usages..."
grep -R --line-number "|tojson" backend/apps/admin_ui/templates || true
