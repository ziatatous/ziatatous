#!/usr/bin/env bash
# Lance ASFALTO : crée l'environnement Python, installe, démarre, ouvre le navigateur.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
(sleep 2; (xdg-open http://127.0.0.1:8000 || open http://127.0.0.1:8000) >/dev/null 2>&1 || true) &
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
