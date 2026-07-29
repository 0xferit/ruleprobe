"""Reading recorded runs, and deriving properties of them.

Owns the answers to "which run is current" and "how many units was it meant to
produce". Both were previously re-derived in each consumer, and the planned-unit
count had already been frozen into a shell script as the literal 756, so a
change to the sample count or the condition list would have desynced the
watchdog from the progress display with no error.
"""

from __future__ import annotations

import json
from pathlib import Path

from ruleprobe.conditions import CONDITION_IDS

RUNS_DIR = Path("runs")
SOLIDITY_SUFFIX = ".sol"


def latest_run(
    runs_dir: Path = RUNS_DIR, solidity_only: bool = False
) -> tuple[Path | None, list[dict]]:
    """The most recent run holding records, newest first."""
    if not runs_dir.exists():
        return None, []

    for directory in sorted(runs_dir.iterdir(), reverse=True):
        records_path = directory / "records.jsonl"
        if not records_path.exists():
            continue
        records = load_records(records_path)
        if not records:
            continue
        if solidity_only and not records[0]["task_id"].endswith(SOLIDITY_SUFFIX):
            continue
        return directory, records
    return None, []


def load_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def planned_units(records: list[dict]) -> int:
    """How many units the run intends to produce.

    Derived from the run's own contents rather than a stored constant: tasks
    seen, the full condition list, and the highest sample index reached. Never
    reports fewer units than are already recorded, since early on only some
    conditions have appeared.
    """
    if not records:
        return 0
    tasks = {r["task_id"] for r in records}
    samples = max(r.get("sample", 0) for r in records) + 1
    return max(len(tasks) * len(CONDITION_IDS) * samples, len(records))
