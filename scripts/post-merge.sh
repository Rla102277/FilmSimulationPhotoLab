#!/usr/bin/env bash
set -euo pipefail

if [[ -f package-lock.json ]]; then
  npm ci --no-audit --no-fund
fi

npm run build