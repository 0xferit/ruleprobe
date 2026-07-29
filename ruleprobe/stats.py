"""Paired summary statistics.

Every condition sees the identical task set, so each task yields one paired
delta against the control. Pairing removes between-task difficulty variance,
which is the dominant noise source when the task count is small.

The bootstrap is stdlib-only and seeded, so a reported interval can be
re-derived exactly from the committed records.
"""

from __future__ import annotations

import random
from statistics import mean

from ruleprobe.conditions import CONDITION_IDS
from ruleprobe.score import CALL_FAILED

BOOTSTRAP_RESAMPLES = 10000
CONFIDENCE = 0.95
DEFAULT_SEED = 20260728


def summarise(records: list[dict]) -> list[dict]:
    """One row per condition, ordered as declared in `conditions.py`."""
    by_condition: dict[str, list[dict]] = {}
    for r in records:
        by_condition.setdefault(r["condition"], []).append(r)

    ordered = [c for c in CONDITION_IDS if c in by_condition]
    ordered += [c for c in by_condition if c not in CONDITION_IDS]

    rows = []
    for condition in ordered:
        group = by_condition[condition]
        scored = [r for r in group if r["kill_rate"] is not None]
        detections = [r.get("detections") or {} for r in group]
        rows.append(
            {
                "condition": condition,
                "n": len(group),
                "valid_rate": sum(1 for r in group if r["valid"]) / len(group),
                "kill_rate": mean(r["kill_rate"] for r in scored) if scored else 0.0,
                "mean_tests": mean(r["tests_collected"] for r in group) if group else 0.0,
                "assert_density": _density(detections),
                "tautological": sum(d.get("tautological", 0) for d in detections),
                "assertion_free": sum(d.get("assertion_free", 0) for d in detections),
                "mocks_sut": sum(d.get("mocks_sut", 0) for d in detections),
                "trivial_assert": sum(d.get("trivial_assert", 0) for d in detections),
                # Kept apart deliberately: an import or collection error means the
                # model broke the mechanical contract, while a failed assertion
                # means it disagreed about behaviour. Merging them would let a
                # renamed import read as a collapse in test quality.
                "invalid_error": sum(
                    1 for r in group if r.get("validity_outcome") in {"error", CALL_FAILED}
                ),
                "invalid_failed": sum(
                    1 for r in group if r.get("validity_outcome") == "failed"
                ),
                "import_violations": sum(1 for r in group if r.get("import_violation")),
                "invalid_other": sum(
                    1
                    for r in group
                    if not r["valid"]
                    and r.get("validity_outcome") not in {"error", CALL_FAILED, "failed"}
                ),
            }
        )
    return rows


def _density(detections: list[dict]) -> float:
    tests = sum(d.get("tests", 0) for d in detections)
    assertions = sum(d.get("assertions", 0) for d in detections)
    return assertions / tests if tests else 0.0


def paired_deltas(
    records: list[dict],
    baseline: str,
    seed: int = DEFAULT_SEED,
) -> dict[str, dict | None]:
    """Mean kill-rate change vs `baseline`, with a bootstrap interval.

    A task contributes only when it produced a valid suite in both arms;
    otherwise the two conditions would be compared on different task sets.
    """
    scores: dict[str, dict[str, float]] = {}
    for r in records:
        if r["kill_rate"] is not None:
            scores.setdefault(r["condition"], {})[r["task_id"]] = r["kill_rate"]

    control = scores.get(baseline, {})
    out: dict[str, dict | None] = {}

    for condition, task_scores in scores.items():
        if condition == baseline:
            continue
        shared = sorted(set(control) & set(task_scores))
        if not shared:
            out[condition] = None
            continue
        deltas = [task_scores[t] - control[t] for t in shared]
        low, high = _bootstrap_interval(deltas, seed)
        out[condition] = {
            "n": len(deltas),
            "mean": mean(deltas),
            "low": low,
            "high": high,
        }
    return out


def _bootstrap_interval(values: list[float], seed: int) -> tuple[float, float]:
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(seed)
    size = len(values)
    means = sorted(
        mean(rng.choice(values) for _ in range(size)) for _ in range(BOOTSTRAP_RESAMPLES)
    )
    tail = (1.0 - CONFIDENCE) / 2
    return means[int(tail * BOOTSTRAP_RESAMPLES)], means[int((1 - tail) * BOOTSTRAP_RESAMPLES) - 1]
