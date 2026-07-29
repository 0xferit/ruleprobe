"""Command line entry point: freeze the data, run the experiment, report it."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from ruleprobe.backend import DEFAULT_MODEL, call_model, extract_code
from ruleprobe.conditions import (
    CONTROL,
    render_solidity_task_prompt,
    load_base_prompt,
    load_conditions,
    render_task_prompt,
)
from ruleprobe.dataset import freeze as freeze_tasks
from ruleprobe.dataset import load as load_tasks
from ruleprobe.normalise import normalise_import
from ruleprobe.score import score_solidity_suite, score_suite
from ruleprobe.stats import paired_deltas, summarise
from ruleprobe.validate import freeze_mutants, load_mutants

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_PATH = REPO_ROOT / "data" / "tasks.jsonl"
MUTANTS_PATH = REPO_ROOT / "data" / "mutants.jsonl"
RUNS_DIR = REPO_ROOT / "runs"
DEFAULT_WORKERS = 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ruleprobe")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("freeze", help="regenerate data/tasks.jsonl and data/mutants.jsonl")

    run = sub.add_parser("run", help="run the experiment")
    run.add_argument("--limit", type=int, default=None, help="use only the first N tasks")
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    run.add_argument("--tasks", type=Path, default=TASKS_PATH)
    run.add_argument("--mutants", type=Path, default=MUTANTS_PATH)
    run.add_argument("--samples", type=int, default=1,
                     help="repeats per (condition, task); the only way to estimate\nrun-to-run variance, since the CLI exposes no temperature control")
    run.add_argument("--lang", choices=["py", "sol"], default="py")
    run.add_argument("--repo", type=Path, default=None,
                     help="Solidity source repo the frozen tasks were sliced from")
    run.add_argument("--only", default=None,
                     help="comma-separated condition ids to run")

    report = sub.add_parser("report", help="summarise a run")
    report.add_argument("run_dir", type=Path, nargs="?", default=None)

    args = parser.parse_args(argv)

    if args.command == "freeze":
        return _freeze()
    if args.command == "run":
        return _run(args.limit, args.model, args.workers, args.tasks, args.mutants,
                    args.samples, args.only, args.lang, args.repo)
    return _report(args.run_dir)


def _freeze() -> int:
    tasks = freeze_tasks(TASKS_PATH)
    print(f"froze {len(tasks)} tasks -> {TASKS_PATH}")
    mutants = freeze_mutants(tasks, MUTANTS_PATH)
    print(f"froze {len(mutants)} killable mutants -> {MUTANTS_PATH}")
    return 0


def _run(
    limit: int | None,
    model: str,
    workers: int,
    tasks_path: Path = TASKS_PATH,
    mutants_path: Path = MUTANTS_PATH,
    samples: int = 1,
    only: str | None = None,
    lang: str = "py",
    repo: Path | None = None,
) -> int:
    tasks = _load_solidity_tasks(tasks_path) if lang == "sol" else load_tasks(tasks_path)
    if limit:
        tasks = tasks[:limit]
    mutants_by_task = load_mutants(mutants_path)
    conditions = load_conditions(lang=lang)
    if only:
        wanted = {c.strip() for c in only.split(",")}
        conditions = [c for c in conditions if c.id in wanted]
    base = load_base_prompt(lang=lang)

    run_dir = RUNS_DIR / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    records_path = run_dir / "records.jsonl"

    units = [(c, t, s) for c in conditions for t in tasks for s in range(samples)]
    print(
        f"{len(units)} units: {len(conditions)} conditions x {len(tasks)} tasks "
        f"x {samples} samples (model={model})"
    )

    spent = 0.0
    done = 0
    with records_path.open("w") as out, ThreadPoolExecutor(max_workers=workers) as pool:
        for record in pool.map(
            lambda unit: _run_unit(
                unit[0], unit[1], base, mutants_by_task, model, unit[2], lang, repo
            ),
            units,
        ):
            out.write(json.dumps(record) + "\n")
            out.flush()
            spent += record["cost_usd"]
            done += 1
            rate = record["kill_rate"]
            shown = "invalid" if rate is None else f"{rate:.2f}"
            print(
                f"[{done}/{len(units)}] {record['condition']:17s} {record['task_id']:14s}"
                f" kill={shown} ${spent:.2f}",
                flush=True,
            )

    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "model": model,
                "tasks": len(tasks),
                "samples": samples,
                "tasks_file": str(tasks_path.name),
                "conditions": [c.id for c in conditions],
                "base_prompt": base,
                "total_cost_usd": round(spent, 4),
            },
            indent=2,
        )
    )
    print(f"\nwrote {records_path}  (${spent:.2f})")
    return _report(run_dir)


def _load_solidity_tasks(path: Path):
    from ruleprobe.solidity import SolidityTask

    with path.open() as f:
        return [SolidityTask(**json.loads(line)) for line in f if line.strip()]


def _run_unit(
    condition,
    task,
    base: str,
    mutants_by_task: dict,
    model: str,
    sample: int = 0,
    lang: str = "py",
    repo: Path | None = None,
) -> dict:
    system_prompt = condition.system_prompt(base)
    if lang == "sol":
        user_prompt = render_solidity_task_prompt(task.contract, task.entry_file, task.source)
        entry_point = task.contract
    else:
        user_prompt = render_task_prompt(task.entry_point, task.full_solution)
        entry_point = task.entry_point

    # A broad catch is deliberate. pool.map propagates any exception and aborts
    # the entire run, so one bad unit out of hundreds must never be able to take
    # the campaign down with it. The cost of over-catching is one lost unit; the
    # cost of under-catching was 756.
    try:
        response = call_model(system_prompt, user_prompt, model, sample=sample)
        error = ""

        raw_test_source = extract_code(response.text)
        mutants = [m.source for m in mutants_by_task.get(task.task_id, [])]

        if lang == "sol":
            test_source, import_violation = raw_test_source, False
            score = score_solidity_suite(
                repo, task.entry_file, task.closure, mutants, test_source, task.contract
            )
        else:
            test_source, import_violation = normalise_import(raw_test_source, task.entry_point)
            score = score_suite(task.full_solution, mutants, test_source, task.entry_point)
    except Exception as exc:
        return _failed_record(
            condition, task, system_prompt, user_prompt, f"{type(exc).__name__}: {exc}",
            sample, entry_point,
        )

    return {
        "condition": condition.id,
        "predicted_failure": condition.predicted_failure,
        "task_id": task.task_id,
        "sample": sample,
        "entry_point": entry_point,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response": response.text,
        "test_source_raw": raw_test_source,
        "test_source": test_source,
        "import_violation": import_violation,
        "cost_usd": response.cost_usd,
        "valid": score.valid,
        "validity_outcome": score.validity_outcome,
        "tests_collected": score.tests_collected,
        "mutants_total": score.mutants_total,
        "mutants_killed": score.mutants_killed,
        "killed_mutants": score.killed_mutants,
        "kill_rate": score.kill_rate,
        "detections": asdict(score.report),
        "error": error,
    }


def _failed_record(
    condition, task, system_prompt, user_prompt, error, sample: int, entry_point: str
) -> dict:
    """A unit that could not be scored, recorded rather than raised.

    Takes `sample` and `entry_point` explicitly: they were previously read as
    free variables belonging to the caller, so this raised NameError the moment
    it was reached, turning every transient model-call failure into a crash
    that aborted the whole run.
    """
    return {
        "condition": condition.id,
        "predicted_failure": condition.predicted_failure,
        "task_id": task.task_id,
        "sample": sample,
        "entry_point": entry_point,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response": "",
        "test_source_raw": "",
        "test_source": "",
        "import_violation": False,
        "cost_usd": 0.0,
        "valid": False,
        "validity_outcome": "call_failed",
        "tests_collected": 0,
        "mutants_total": 0,
        "mutants_killed": 0,
        "killed_mutants": [],
        "kill_rate": None,
        "detections": {},
        "error": error,
    }


def _latest_run() -> Path:
    runs = sorted(p for p in RUNS_DIR.iterdir() if (p / "records.jsonl").exists())
    if not runs:
        raise SystemExit("no runs found")
    return runs[-1]


def _report(run_dir: Path | None) -> int:
    run_dir = run_dir or _latest_run()
    records = [
        json.loads(line)
        for line in (run_dir / "records.jsonl").read_text().splitlines()
        if line.strip()
    ]

    table = summarise(records)
    deltas = paired_deltas(records, baseline=CONTROL)

    lines = [
        f"# ruleprobe results — {run_dir.name}",
        "",
        "Kill rate is the share of killable mutants the suite caught, averaged over tasks.",
        "Only suites that pass the correct implementation are scored; the rest are counted",
        "as invalid and excluded from kill rate.",
        "",
        "| condition | valid | kill rate | Δ vs control | 95% CI | n | tests | asserts/test | invalid: error | invalid: assert | wrong import | tautological | mocks SUT |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in table:
        d = deltas.get(row["condition"])
        delta = "—" if d is None else f"{d['mean']:+.3f}"
        ci = "—" if d is None else f"[{d['low']:+.3f}, {d['high']:+.3f}]"
        paired_n = "—" if d is None else str(d["n"])
        lines.append(
            f"| `{row['condition']}` | {row['valid_rate']:.0%} | {row['kill_rate']:.3f} | {delta} | {ci} "
            f"| {paired_n} | {row['mean_tests']:.1f} | {row['assert_density']:.2f} "
            f"| {row['invalid_error']} | {row['invalid_failed']} | {row['import_violations']} "
            f"| {row['tautological']} | {row['mocks_sut']} |"
        )
    lines += [
        "",
        "`invalid: error` counts suites that failed to import or collect — a broken",
        "mechanical contract, not a judgement about behaviour. `invalid: assert` counts",
        "suites that ran but disagreed with the correct implementation. Both are excluded",
        "from kill rate; only the second is evidence about test quality.",
        "",
        "`wrong import` counts suites that ignored the explicit `from solution import ...`",
        "contract in the user prompt. Those imports are rewritten before scoring so that",
        "test quality can be measured separately; no assertion is altered.",
    ]

    text = "\n".join(lines) + "\n"
    (run_dir / "report.md").write_text(text)
    print("\n" + text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
