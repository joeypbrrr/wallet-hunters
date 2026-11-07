#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .run/hourly.pid ]]; then
  pid=$(cat .run/hourly.pid)
  if [[ -r /proc/$pid/cmdline ]] && tr '\0' ' ' </proc/$pid/cmdline | grep -q 'scripts/hourly-loop.sh'; then kill -TERM "$pid"; fi
  rm -f .run/hourly.pid
fi
echo 'Hourly schedule OFF; an already running research snapshot may finish.'
