#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-5000}"
exec python -m uvicorn server.main:app --host 0.0.0.0 --port "$PORT"
