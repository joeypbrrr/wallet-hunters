#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .run
exec 9>.run/cycle.lock
flock -n 9 || { echo 'Another cycle is already running'; exit 1; }
python3 pipeline.py
if [[ "${1:-}" == '--push' ]]; then
  git add data config.json
  if ! git diff --cached --quiet; then
    git commit -m "Research snapshot $(TZ=America/New_York date '+%Y-%m-%d %H:%M:%S %Z')"
    git push origin main
  fi
fi
