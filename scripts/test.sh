#!/usr/bin/env bash
# Full test suite: backend pytest + frontend production build.
# SKIP_WEB=1 scripts/test.sh   -> backend tests only (faster)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Backend tests"
.venv/bin/python -m pytest

if [ "${SKIP_WEB:-0}" = "1" ]; then
  echo "==> Frontend build skipped (SKIP_WEB=1)"
  exit 0
fi

echo "==> Frontend production build"
if [ ! -d apps/web/node_modules ]; then
  echo "ERROR: apps/web/node_modules missing — run scripts/setup.sh first."
  exit 1
fi
(cd apps/web && npm run build)

echo "All tests passed."
