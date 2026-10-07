#!/usr/bin/env bash
# Run API + web together for local development.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  echo "ERROR: .venv missing — run scripts/setup.sh first."
  exit 1
fi
if [ ! -f .env ]; then
  cp .env.example .env
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

mkdir -p data
.venv/bin/python -m alembic -c database/alembic.ini upgrade head

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"

echo "==> JARVIS dev: API http://127.0.0.1:${API_PORT}  ·  Web http://127.0.0.1:${WEB_PORT}"

.venv/bin/python -m uvicorn apps.api.main:app \
  --host "${API_HOST:-127.0.0.1}" --port "${API_PORT}" &
API_PID=$!

(cd apps/web && npm run dev -- --port "${WEB_PORT}") &
WEB_PID=$!

cleanup() {
  kill "${API_PID}" "${WEB_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
