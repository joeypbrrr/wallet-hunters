#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p .run
exec 8>.run/scheduler.lock
flock -n 8 || { echo 'Wallet Hunters scheduler already locked'; exit 1; }
trap 'exit 0' TERM INT
if [[ "${1:-}" == '--delay-first' ]]; then
  echo $(( $(date +%s) + 3600 )) > .run/next-cycle-epoch
  sleep 3600 & wait $!
fi
while true; do
  start=$(date +%s)
  ./scripts/run-once.sh --push || echo "Cycle failed at $(date -Is)"
  elapsed=$(( $(date +%s) - start ))
  waitfor=$((3600-elapsed)); ((waitfor<60)) && waitfor=60
  echo $(( $(date +%s) + waitfor )) > .run/next-cycle-epoch
  sleep "$waitfor" & wait $!
done
