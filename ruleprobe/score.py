"""Turns one generated suite into one row of evidence.

Kill rate is the primary measure: of the mutants known to be killable, how many
does this suite actually catch. It is only defined for a suite that first
passes the correct implementation, because a suite that reds out on correct
code reds out on every mutant too and would otherwise score perfectly.
"""

from __future__ import annotations

from dataclasses import dataclass

from ruleprobe.detect import Report, analyze
from ruleprobe.execute import DEFAULT_TIMEOUT_SECONDS, Outcome, run_suite


@dataclass(frozen=True)
class Score:
    valid: bool
    validity_outcome: str
    tests_collected: int
    mutants_total: int
    mutants_killed: int
    killed_mutants: list[bool]
    report: Report

    @property
    def kill_rate(self) -> float | None:
        """Undefined for an invalid suite; never zero-by-default."""
        if not self.valid or self.mutants_total == 0:
            return None
        return self.mutants_killed / self.mutants_total


def score_suite(
    solution_source: str,
    mutant_sources: list[str],
    test_source: str,
    entry_point: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Score:
    report = analyze(test_source, entry_point)
    validity = run_suite(solution_source, test_source, timeout_seconds)
    valid = validity.outcome is Outcome.PASSED

    killed_mutants: list[bool] = []
    if valid:
        for mutant in mutant_sources:
            result = run_suite(mutant, test_source, timeout_seconds)
            # The suite passes correct code, so any other verdict here is
            # attributable to the mutation.
            killed_mutants.append(result.outcome is not Outcome.PASSED)

    return Score(
        valid=valid,
        validity_outcome=validity.outcome.value,
        tests_collected=validity.tests_collected,
        mutants_total=len(mutant_sources) if valid else 0,
        mutants_killed=sum(killed_mutants),
        killed_mutants=killed_mutants,
        report=report,
    )


def score_solidity_suite(
    repo_root,
    entry_file,
    closure,
    mutant_sources: list[str],
    test_source: str,
    contract: str,
) -> Score:
    """Solidity counterpart of `score_suite`, producing the identical record.

    Same validity gate for the same reason: a suite that fails to build or fails
    against the unmutated contract fails against every mutant too, and without
    the gate would score as the strongest suite in the experiment.
    """
    import tempfile
    from pathlib import Path

    from ruleprobe.detect import Report
    from ruleprobe.solidity import assemble_project, run_forge_test

    repo_root = Path(repo_root)
    entry = repo_root / entry_file
    paths = {repo_root / c for c in closure}
    empty = Report(0, 0, 0, 0, 0, 0)

    with tempfile.TemporaryDirectory(prefix="ruleprobe-sol-") as workdir:
        work = Path(workdir)
        assemble_project(work, repo_root, paths, test_source)
        baseline = run_forge_test(work)

    valid = baseline.outcome == "passed"
    killed: list[bool] = []
    if valid:
        for mutant in mutant_sources:
            with tempfile.TemporaryDirectory(prefix="ruleprobe-sol-") as workdir:
                work = Path(workdir)
                assemble_project(work, repo_root, paths, test_source, overrides={entry: mutant})
                result = run_forge_test(work)
            killed.append(result.outcome != "passed")

    return Score(
        valid=valid,
        validity_outcome=baseline.outcome,
        tests_collected=baseline.tests_run,
        mutants_total=len(mutant_sources) if valid else 0,
        mutants_killed=sum(killed),
        killed_mutants=killed,
        report=empty,
    )


# --- Score cache -------------------------------------------------------
#
# Scoring is deterministic in (task, mutant set, suite), and it is the slow
# half of a unit: a model response is cached, but re-running forge or pytest
# over an already-scored unit is not. Without this, every relaunch replays the
# entire completed prefix, and the replay grows with each restart.

import json
from dataclasses import asdict
from pathlib import Path

from ruleprobe.cache import SCORE_CACHE_DIR, cache_key


def score_key(lang: str, task_id: str, mutant_sources: list[str], test_source: str) -> str:
    """Identity of a scoring job.

    The mutant set is part of the key: a score carried over to a changed set of
    mutants would silently misreport kill rate, which is the headline number.
    """
    return cache_key([lang, task_id, list(mutant_sources), test_source])


def read_score_cache(cache_dir: Path, key: str) -> Score | None:
    path = Path(cache_dir) / f"{key}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
        # Reconstructed generically, mirroring asdict on the way out. Restating
        # the field list here would mean a new Score field silently produced
        # cache misses instead of an error.
        payload["report"] = Report(**payload["report"])
        return Score(**payload)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def write_score_cache(cache_dir: Path, key: str, score: Score) -> None:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(json.dumps(asdict(score)))
