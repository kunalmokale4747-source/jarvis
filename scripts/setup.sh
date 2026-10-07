#!/usr/bin/env bash
# One-time setup: python env + dependencies + database + frontend deps.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Python virtualenv"
if [ ! -d .venv ]; then
  python3 -m venv .venv || {
    echo "ERROR: python3-venv is not installed. Run: apt install python3.13-venv"
    exit 1
  }
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[dev]"

echo "==> Local env file"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    created .env from .env.example (all secrets empty — fill as needed)"
fi

echo "==> Database migrations"
mkdir -p data
.venv/bin/python -m alembic -c database/alembic.ini upgrade head

echo "==> Frontend dependencies"
if [ ! -d apps/web/node_modules ]; then
  (cd apps/web && npm install)
fi

echo ""
echo "Setup complete."
echo "  Start everything : scripts/dev.sh"
echo "  Run tests        : scripts/test.sh"
