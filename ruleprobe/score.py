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
