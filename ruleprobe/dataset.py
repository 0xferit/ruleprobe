"""Freezes a compact, reproducible task set from HumanEval+.

The frozen `data/tasks.jsonl` is committed so a run reproduces without
network access and without depending on the upstream dataset staying put.
"""

from __future__ import annotations

import ast
import json
import random
from dataclasses import dataclass, asdict
from pathlib import Path

DATASET_ID = "evalplus/humanevalplus"
DATASET_REVISION = "d32357cf319e50e9c8d8dab5ea876c72b0fd321b"
DATASET_FILE = "data/test-00000-of-00001-5973903632b82d40.parquet"

COMPLEXITY_BUCKETS = 3
DEFAULT_SAMPLE_SIZE = 24
DEFAULT_SEED = 20260728


@dataclass(frozen=True)
class Task:
    task_id: str
    entry_point: str
    prompt: str
    canonical_solution: str

    @property
    def full_solution(self) -> str:
        """The complete, correct module: signature, docstring, and body."""
        return self.prompt + self.canonical_solution


def _ast_size(source: str) -> int:
    return sum(1 for _ in ast.walk(ast.parse(source)))


def freeze(
    out_path: Path,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    seed: int = DEFAULT_SEED,
) -> list[Task]:
    """Downloads the pinned dataset revision and writes a stratified sample.

    Stratification is by AST size of the complete solution, so the sample
    is not accidentally all one-liners.
    """
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq

    local = hf_hub_download(
        DATASET_ID, DATASET_FILE, repo_type="dataset", revision=DATASET_REVISION
    )
    rows = pq.read_table(local).to_pylist()

    candidates = [
        Task(
            task_id=r["task_id"],
            entry_point=r["entry_point"],
            prompt=r["prompt"],
            canonical_solution=r["canonical_solution"],
        )
        for r in rows
    ]
    candidates = [t for t in candidates if _is_parseable(t)]
    selected = _stratified_sample(candidates, sample_size, seed)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for t in selected:
            f.write(json.dumps(asdict(t)) + "\n")
    return selected


def _is_parseable(task: Task) -> bool:
    try:
        ast.parse(task.full_solution)
        return True
    except SyntaxError:
        return False


def _stratified_sample(tasks: list[Task], sample_size: int, seed: int) -> list[Task]:
    ranked = sorted(tasks, key=lambda t: (_ast_size(t.full_solution), t.task_id))
    bucket_size = len(ranked) // COMPLEXITY_BUCKETS
    rng = random.Random(seed)

    picked: list[Task] = []
    per_bucket = sample_size // COMPLEXITY_BUCKETS
    for i in range(COMPLEXITY_BUCKETS):
        start = i * bucket_size
        end = len(ranked) if i == COMPLEXITY_BUCKETS - 1 else start + bucket_size
        picked.extend(rng.sample(ranked[start:end], per_bucket))

    remainder = sample_size - len(picked)
    if remainder:
        rest = [t for t in ranked if t not in picked]
        picked.extend(rng.sample(rest, remainder))

    return sorted(picked, key=lambda t: int(t.task_id.split("/")[1]))


def load(path: Path) -> list[Task]:
    with path.open() as f:
        return [Task(**json.loads(line)) for line in f if line.strip()]
