"""Runs a generated pytest suite against a candidate solution module.

Every suite here is model-written code executed on the host. The subprocess,
timeout and CPU cap below are damage limiting, not a security boundary; see
the sandboxing note in SCORING.md before running this on untrusted output.
"""

from __future__ import annotations

import json
import re
import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 30
CPU_SECONDS_LIMIT = 60
MEMORY_BYTES_LIMIT = 2 * 1024 * 1024 * 1024

PYTEST_EXIT_OK = 0
PYTEST_EXIT_TESTS_FAILED = 1
PYTEST_EXIT_INTERRUPTED = 2
PYTEST_EXIT_INTERNAL_ERROR = 3
PYTEST_EXIT_USAGE_ERROR = 4
PYTEST_EXIT_NO_TESTS_COLLECTED = 5

SOLUTION_MODULE = "solution"
TEST_FILENAME = "test_generated.py"

_COLLECTED = re.compile(r"collected (\d+) item")
_OUTCOME_COUNTS = re.compile(r"(\d+) (passed|failed|error|errors|xfailed|xpassed)\b")


class Outcome(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"
    NO_TESTS = "no_tests"


@dataclass(frozen=True)
class SuiteResult:
    outcome: Outcome
    tests_collected: int
    detail: str


def run_suite(
    solution_source: str,
    test_source: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> SuiteResult:
    """Executes `test_source` against `solution_source` in a fresh directory."""
    with tempfile.TemporaryDirectory(prefix="ruleprobe-") as workdir:
        root = Path(workdir)
        (root / f"{SOLUTION_MODULE}.py").write_text(solution_source)
        (root / TEST_FILENAME).write_text(test_source)

        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", TEST_FILENAME, "-q", "-p", "no:cacheprovider"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                preexec_fn=_apply_resource_limits,
            )
        except subprocess.TimeoutExpired:
            return SuiteResult(Outcome.TIMEOUT, 0, f"exceeded {timeout_seconds}s")

        output = completed.stdout + completed.stderr
        return SuiteResult(
            outcome=_classify(completed.returncode),
            tests_collected=_count_collected(output),
            detail=output[-2000:],
        )


def _classify(return_code: int) -> Outcome:
    if return_code == PYTEST_EXIT_OK:
        return Outcome.PASSED
    if return_code == PYTEST_EXIT_TESTS_FAILED:
        return Outcome.FAILED
    if return_code == PYTEST_EXIT_NO_TESTS_COLLECTED:
        return Outcome.NO_TESTS
    return Outcome.ERROR


def _count_collected(output: str) -> int:
    """Number of tests pytest actually ran.

    `-q` omits the "collected N items" line on a clean run, so the summary
    counts are the fallback.
    """
    match = _COLLECTED.search(output)
    if match:
        return int(match.group(1))
    return sum(int(count) for count, _outcome in _OUTCOME_COUNTS.findall(output))


def _apply_resource_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS_LIMIT, CPU_SECONDS_LIMIT))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES_LIMIT, MEMORY_BYTES_LIMIT))
    except (ValueError, OSError):
        # macOS rejects RLIMIT_AS for some values; the wall-clock timeout and
        # CPU cap remain in force.
        pass
