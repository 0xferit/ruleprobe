"""Keeps only the mutants a thorough suite can actually kill.

A mutant that is semantically equivalent to the original is unkillable by any
test, so leaving it in would depress every condition's score and understate
what a good suite achieves. HumanEval+'s expanded reference suite is the
oracle: if it cannot tell the mutant from the original, the mutant is dropped.

Output is frozen to data/mutants.jsonl and committed, so experiment runs need
neither this module nor numpy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from ruleprobe.dataset import (
    DATASET_FILE,
    DATASET_ID,
    DATASET_REVISION,
    Task,
)
from ruleprobe.execute import SOLUTION_MODULE, Outcome, run_suite
from ruleprobe.mutate import (
    DEFAULT_MAX_MUTANTS_PER_TASK,
    DEFAULT_MUTANT_SEED,
    generate_mutants,
)

REFERENCE_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class ValidatedMutant:
    task_id: str
    operator: str
    source: str


def reference_wrapper(reference_test: str, entry_point: str) -> str:
    """Wraps HumanEval+'s `check(candidate)` harness as a pytest test."""
    return (
        f"from {SOLUTION_MODULE} import {entry_point}\n"
        f"{reference_test}\n\n"
        f"def test_reference():\n"
        f"    check({entry_point})\n"
    )


def freeze_mutants(tasks: list[Task], out_path: Path) -> list[ValidatedMutant]:
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq

    local = hf_hub_download(
        DATASET_ID, DATASET_FILE, repo_type="dataset", revision=DATASET_REVISION
    )
    reference = {r["task_id"]: r["test"] for r in pq.read_table(local).to_pylist()}

    validated: list[ValidatedMutant] = []
    for task in tasks:
        wrapper = reference_wrapper(reference[task.task_id], task.entry_point)

        baseline = run_suite(task.full_solution, wrapper, REFERENCE_TIMEOUT_SECONDS)
        if baseline.outcome is not Outcome.PASSED:
            raise RuntimeError(
                f"{task.task_id}: reference suite does not pass the canonical "
                f"solution ({baseline.outcome}); the oracle cannot be trusted"
            )

        for mutant in generate_mutants(
            task.full_solution, DEFAULT_MAX_MUTANTS_PER_TASK, DEFAULT_MUTANT_SEED
        ):
            result = run_suite(mutant.source, wrapper, REFERENCE_TIMEOUT_SECONDS)
            if result.outcome is not Outcome.PASSED:
                validated.append(
                    ValidatedMutant(task.task_id, mutant.operator, mutant.source)
                )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for m in validated:
            f.write(json.dumps(asdict(m)) + "\n")
    return validated


def load_mutants(path: Path) -> dict[str, list[ValidatedMutant]]:
    by_task: dict[str, list[ValidatedMutant]] = {}
    with path.open() as f:
        for line in f:
            if line.strip():
                m = ValidatedMutant(**json.loads(line))
                by_task.setdefault(m.task_id, []).append(m)
    return by_task
