#!/usr/bin/env bash
# Waits for the in-flight campaign, then keeps relaunching until complete.
#
# Distinct from overnight.sh: it never starts a second campaign alongside a
# running one, and enforces no cost cap. Progress is measured from the records
# file, so a relaunch resumes from cache and pays only for what is missing.
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
LOG_DIR="${LOG_DIR:-/tmp}"
LOG="$LOG_DIR/watchdog.log"
# Derived, never hardcoded: a change to the sample count, the condition list or
# the feasible task set must not silently desync the watchdog from the run.
TARGET="${TARGET:-$("${PY:-.venv/bin/python}" -c '
import sys; sys.path.insert(0, ".")
from ruleprobe.runs import latest_run, planned_units
print(planned_units(latest_run()[1]))')}"

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

# Counts records that carry a result. A raw line count treats a failed model
# call as progress, so a run whose calls were all rate-limited reports itself
# complete with no data in it.
progress() {
  "$PY" -c 'import sys; sys.path.insert(0, ".")
from ruleprobe.runs import latest_run, usable_units
print(usable_units(latest_run()[1]))' 2>/dev/null || echo 0
}

log "watchdog started, target $TARGET units"
for round in $(seq 1 20); do
  # Never run two campaigns at once.
  while pgrep -f "ruleprobe run" > /dev/null; do sleep 60; done

  done_units=$(progress)
  log "round $round: $done_units/$TARGET units complete"
  if [ "$done_units" -ge "$TARGET" ]; then
    log "campaign complete"
    break
  fi

  log "relaunching campaign"
  ./scripts/campaign.sh sol >> "$LOG_DIR/overnight-campaign.log" 2>&1
  sleep 15
done

log "writing MORNING-REPORT.md"
"$PY" scripts/morning_report.py >> "$LOG" 2>&1
log "done"
