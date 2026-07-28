#!/usr/bin/env bash
# Unattended overnight driver.
#
# Runs the phase-1 campaign to completion, restarting on crash, and writes
# MORNING-REPORT.md whether it finishes, stalls, or hits the cost cap. It must
# not depend on any interactive session staying alive.
set -uo pipefail
cd "$(dirname "$0")/.."

LOG_DIR="${LOG_DIR:-/tmp}"
SCREEN_LOG="${SCREEN_LOG:-$LOG_DIR/screen.log}"
CAMPAIGN_LOG="$LOG_DIR/overnight-campaign.log"
COST_CAP="${COST_CAP:-350}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-8}"
PY="${PY:-.venv/bin/python}"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$CAMPAIGN_LOG"; }

# 1. Wait for the feasibility screen to finish writing its task list.
log "waiting for feasibility screen"
for _ in $(seq 1 240); do
  [ -s data/tasks-sol-feasible.jsonl ] && break
  sleep 30
done
if [ ! -s data/tasks-sol-feasible.jsonl ]; then
  log "screen produced no task list; falling back to the unscreened set"
fi

# 2. Run the campaign, restarting on crash. The response cache makes every
#    retry cheap: only cells not already completed cost anything.
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  spent=$("$PY" scripts/spend.py 2>/dev/null || echo 0)
  if awk "BEGIN{exit !($spent > $COST_CAP)}"; then
    log "cost cap reached (\$$spent > \$$COST_CAP); stopping before attempt $attempt"
    break
  fi

  log "campaign attempt $attempt (spent so far \$$spent)"
  if ./scripts/campaign.sh sol >> "$CAMPAIGN_LOG" 2>&1; then
    log "campaign completed on attempt $attempt"
    break
  fi
  log "attempt $attempt exited non-zero; retrying from cache"
  sleep 20
done

# 3. Always produce a report, whatever happened above.
log "writing MORNING-REPORT.md"
"$PY" scripts/morning_report.py >> "$CAMPAIGN_LOG" 2>&1 || log "report generation failed"
log "done"
