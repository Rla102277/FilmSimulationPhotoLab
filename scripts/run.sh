#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-5000}"
if command -v npm >/dev/null 2>&1 && [[ -f package.json ]]; then
  npm run build
fi
exec python -m uvicorn server.main:app --host 0.0.0.0 --port "$PORT"
