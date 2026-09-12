#!/usr/bin/env bash
# Start the API. Keys live in .env.local so `cp .env.example .env` cannot wipe them.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp -n .env.example .env
  echo "Created .env from .env.example."
fi
if [[ ! -f .env.local ]]; then
  echo "Missing .env.local — put API keys there (not in .env)."
fi

exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
