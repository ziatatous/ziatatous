#!/usr/bin/env bash
# NETWATCH launcher (Linux / macOS). One command: installs what is missing, starts backend + UI, opens the browser.
set -e
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
if ! command -v "$PY" >/dev/null 2>&1; then echo "Python 3.12+ not found. Install it from https://www.python.org/downloads/ (see README.md)"; exit 1; fi
"$PY" - <<'PYEOF' || { echo "Python 3.12 or newer is required (see README.md)"; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)
PYEOF

if [ ! -d .venv ]; then echo "› creating Python environment (first run only)…"; "$PY" -m venv .venv; fi
if [ ! -f .venv/.deps-ok ] || [ backend/requirements.txt -nt .venv/.deps-ok ]; then
  echo "› installing Python dependencies…"
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r backend/requirements.txt
  touch .venv/.deps-ok
fi

if [ ! -f .env ] && [ -f .env.example ]; then cp .env.example .env; echo "› created .env from .env.example (edit it to add free API keys)"; fi

# Frontend: use the prebuilt UI if present, otherwise build it (needs Node.js 20+)
if [ "$1" = "--rebuild" ] || [ ! -f frontend/dist/index.html ]; then
  if ! command -v npm >/dev/null 2>&1; then echo "Node.js 20+ is needed once to build the interface: https://nodejs.org/ (see README.md)"; exit 1; fi
  echo "› building the interface (first run only, ~1 minute)…"
  (cd frontend && npm install --no-audit --no-fund --silent && npm run build --silent)
fi

PORT=$(grep -E '^NETWATCH_PORT=' .env 2>/dev/null | cut -d= -f2); PORT=${PORT:-8000}
URL="http://127.0.0.1:$PORT"
( sleep 3; (command -v xdg-open >/dev/null && xdg-open "$URL") || (command -v open >/dev/null && open "$URL") || true ) >/dev/null 2>&1 &
echo "› NETWATCH running on $URL  (Ctrl+C to stop)"
cd backend && exec ../.venv/bin/python -m app.main "$@"
