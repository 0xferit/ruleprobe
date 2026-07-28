"""Feasibility screen: which Solidity tasks can be unit tested in isolation?

Strategy and factory contracts in a DeFi codebase often need live protocol
addresses or forked state. A generated suite for one cannot compile, so the task
yields no information under any condition and only burns budget.

The screener is a prompt outside the experiment. Screening on a condition's own
success would select tasks that condition handles well, biasing the comparison.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ruleprobe.backend import call_model, extract_code
from ruleprobe.conditions import load_screen_prompt, render_solidity_task_prompt
from ruleprobe.score import score_solidity_suite

REPO = Path(sys.argv[1])
TASKS = Path("data/tasks-sol.jsonl")
OUT = Path("data/tasks-sol-feasible.jsonl")

tasks = [json.loads(line) for line in TASKS.read_text().splitlines() if line.strip()]
system = load_screen_prompt()


def screen(task):
    prompt = render_solidity_task_prompt(task["contract"], task["entry_file"], task["source"])
    try:
        response = call_model(system, prompt)
    except Exception as exc:  # a screening failure is not a task property
        return task, None, f"call failed: {exc}"
    score = score_solidity_suite(
        REPO, task["entry_file"], task["closure"], [], extract_code(response.text), task["contract"]
    )
    return task, score.valid, score.validity_outcome


kept = []
with ThreadPoolExecutor(max_workers=6) as pool:
    for task, valid, outcome in pool.map(screen, tasks):
        print(f"  {'KEEP' if valid else 'DROP'}  {outcome:10s} {task['contract']}", flush=True)
        if valid:
            kept.append(task)

OUT.write_text("".join(json.dumps(t) + "\n" for t in kept))
print(f"\nfeasible: {len(kept)}/{len(tasks)} -> {OUT}")
