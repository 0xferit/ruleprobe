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

case "$PHASE" in
  sol)
    # Phase 1: all nine conditions against the Solidity task set.
    "$PY" -m ruleprobe run \
      --lang sol --repo "$OCTANT" \
      --tasks data/tasks-sol.jsonl --mutants data/mutants-sol.jsonl \
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
