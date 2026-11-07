#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
trap 'exit 0' TERM INT
while true; do
  start=$(date +%s)
  ./scripts/run-once.sh --push || echo "Cycle failed at $(date -Is)"
  elapsed=$(( $(date +%s) - start ))
  waitfor=$((3600-elapsed)); ((waitfor<60)) && waitfor=60
  sleep "$waitfor" & wait $!
done
