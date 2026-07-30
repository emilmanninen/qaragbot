#!/usr/bin/env bash
set -euo pipefail

# Run from repo root regardless of where this script is invoked from,
# since main.py does `from backend.app...` imports.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

source backend/.venv/bin/activate

# --timeout-keep-alive raised past uvicorn's 5s default: idle time between
# chat turns (reading the answer, typing the next question) routinely
# exceeds 5s, and a stale pooled connection from the Next.js dev proxy
# reused after the server already closed it causes an ECONNRESET.
exec uvicorn backend.app.main:app --reload --port 8000 --timeout-keep-alive 75
