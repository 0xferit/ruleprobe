#!/usr/bin/env bash
# Resumable campaign driver.
#
# Every model response is cached by (system prompt, user prompt, model, sample),
# so re-running costs nothing for work already done and only new cells hit the
# API. That makes this safe to invoke repeatedly from a scheduler: each run
# makes progress, and a run that dies loses at most the calls in flight.
set -uo pipefail
cd "$(dirname "$0")/.."

OCTANT="${OCTANT:-/Users/ferit/Library/Mobile Documents/com~apple~CloudDocs/Projects/golemfoundation/octant-v2-core}"
PY="${PY:-.venv/bin/python}"
SAMPLES="${SAMPLES:-3}"
WORKERS="${WORKERS:-6}"
PHASE="${1:-sol}"

# Killing the orchestrator orphans its forge/solc/claude children rather than
# reaping them, and the watchdog relaunches on crash, so they accumulate across
# restarts: load climbs while throughput does not. Clear stragglers first.
# `claude -p` is only ever a harness call; an interactive session is not -p.
# Patterns come from the modules that build the invocations, so a change to
# either command cannot leave this silently matching nothing.
CLAUDE_PATTERN=$("${PY:-.venv/bin/python}" -c 'import sys; sys.path.insert(0,"."); from ruleprobe.backend import PROCESS_PATTERN; print(PROCESS_PATTERN)')
FORGE_PATTERN=$("${PY:-.venv/bin/python}" -c 'import sys; sys.path.insert(0,"."); from ruleprobe.solidity import PROCESS_PATTERN; print(PROCESS_PATTERN)')
reap() {
  pkill -9 -f "$FORGE_PATTERN" 2>/dev/null
  pkill -9 -f "$CLAUDE_PATTERN" 2>/dev/null
  sleep 2
}
reap
trap reap EXIT INT TERM

case "$PHASE" in
  sol)
    # Phase 1: all nine conditions against the Solidity task set.
    # Prefer the feasibility-screened list. Contracts needing live protocol
    # state cannot be tested in isolation under any condition, so they yield no
    # information and only dilute every average.
    TASKS=data/tasks-sol.jsonl
    [ -s data/tasks-sol-feasible.jsonl ] && TASKS=data/tasks-sol-feasible.jsonl
    echo "using task file: $TASKS"
    "$PY" -m ruleprobe run \
      --lang sol --repo "$OCTANT" \
      --tasks "$TASKS" --mutants data/mutants-sol.jsonl \
      --samples "$SAMPLES" --workers "$WORKERS"
    ;;
  py)
    "$PY" -m ruleprobe run \
      --tasks data/tasks-bmk.jsonl --mutants data/mutants-bmk.jsonl \
      --samples "$SAMPLES" --workers "$WORKERS"
    ;;
  *)
    echo "usage: $0 [sol|py]" >&2; exit 2 ;;
esac
