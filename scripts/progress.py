"""Live progress for a running campaign.

Run it any time:            .venv/bin/python scripts/progress.py
Refresh every 30 seconds:   watch -n30 .venv/bin/python scripts/progress.py

Rate and ETA come from the delta between successive invocations, recorded in a
small state file, so the first run shows no rate and every run after it does.
"""

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ruleprobe.conditions import CONDITION_IDS
from ruleprobe.runs import latest_run, planned_units

STATE = Path(".progress-state.json")
BAR_WIDTH = 44
STALL_SECONDS = 600


def bar(fraction: float) -> str:
    filled = int(fraction * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def rate_and_eta(done: int, remaining: int) -> tuple[str, str]:
    now = time.time()
    previous = None
    if STATE.exists():
        try:
            previous = json.loads(STATE.read_text())
        except json.JSONDecodeError:
            previous = None
    STATE.write_text(json.dumps({"time": now, "done": done}))

    if not previous or done <= previous["done"]:
        elapsed = now - previous["time"] if previous else 0
        if previous and elapsed > STALL_SECONDS:
            return "stalled", f"no new units in {elapsed / 60:.0f} min"
        return "—", "—"

    elapsed = now - previous["time"]
    per_minute = (done - previous["done"]) / (elapsed / 60)
    if per_minute <= 0:
        return "—", "—"
    minutes_left = remaining / per_minute
    return f"{per_minute:.1f} units/min", f"{minutes_left / 60:.1f} h"


def main() -> None:
    directory, records = latest_run()
    if not records:
        print("no run found")
        return

    total = planned_units(records)
    done = len(records)
    fraction = done / total if total else 0
    spent = sum(r.get("cost_usd") or 0.0 for r in records)
    fresh = [r for r in records if (r.get("cost_usd") or 0) > 0]
    unit_cost = spent / len(fresh) if fresh else 0
    speed, eta = rate_and_eta(done, total - done)

    print(f"\n  run {directory.name}")
    print(f"  [{bar(fraction)}] {fraction:5.1%}  {done}/{total}")
    print(
        f"  spent ${spent:,.2f}   ${unit_cost:.2f}/unit   "
        f"projected ${spent + (total - done) * unit_cost:,.0f}"
    )
    print(f"  rate {speed}   eta {eta}")

    alive = os.popen("pgrep -f 'ruleprobe run' | wc -l").read().strip()
    calls = os.popen("pgrep -f 'claude -p' | wc -l").read().strip()
    print(f"  campaign {'running' if alive != '0' else 'NOT RUNNING'}   {calls} calls in flight")

    grouped = defaultdict(list)
    for record in records:
        grouped[record["condition"]].append(record)

    print(f"\n  {'condition':22s} {'units':>6s} {'valid':>6s} {'kill':>6s}")
    for condition in CONDITION_IDS:
        group = grouped.get(condition)
        if not group:
            print(f"  {condition:22s} {'—':>6s} {'—':>6s} {'—':>6s}")
            continue
        scored = [r["kill_rate"] for r in group if r["kill_rate"] is not None]
        valid = sum(1 for r in group if r["valid"]) / len(group)
        kill = f"{sum(scored) / len(scored):.3f}" if scored else "—"
        print(f"  {condition:22s} {len(group):6d} {valid:5.0%} {kill:>7s}")
    print()


if __name__ == "__main__":
    main()
