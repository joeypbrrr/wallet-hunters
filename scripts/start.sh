#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "${1:-}" == '--approved' ]] || { echo 'Schedule is OFF. Explicit owner approval required: ./scripts/start.sh --approved'; exit 1; }
mkdir -p .run
if [[ -f .run/hourly.pid ]] && kill -0 "$(cat .run/hourly.pid)" 2>/dev/null; then echo 'Already running'; exit 0; fi
nohup ./scripts/hourly-loop.sh >>.run/hourly.log 2>&1 &
echo $! >.run/hourly.pid
echo "Started local hourly runner PID $!; machine must stay online."
