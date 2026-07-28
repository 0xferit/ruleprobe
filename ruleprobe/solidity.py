"""Solidity task extraction and execution, for the domain the rules were written for.

The Python task set tops out at 8 usable functions, and the variance pilot put
the resolution threshold at roughly 33 tasks for small effects. Solidity is
where the task supply is, and it is also the domain `CLAUDE.md` actually
describes: Rule #4 cites `type(uint256).max`, constructor invariants, and
user-visible reverts.

A task is one contract plus the transitive closure of the project-local files
it imports, assembled into a minimal Foundry project. External dependencies
resolve through remappings rather than being copied. The full octant project
builds in 13.5s; a minimal one runs `forge test` in 0.33s warm, which is what
makes mutation scoring affordable.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

IMPORT_PATTERN = re.compile(r'^\s*import\s+[^"\']*["\']([^"\']+)["\']', re.M)
SOURCE_ROOT = "src"
FOUNDRY_CONFIG = """[profile.default]
src = "src"
out = "out"
libs = []
solc = "{solc}"
auto_detect_solc = false
optimizer = false
ast = true
fuzz = {{ runs = {fuzz_runs} }}
"""
DEFAULT_SOLC = "0.8.33"
# Mutation scoring only needs a mutant distinguished, not a bug hunt, and fuzz
# runs multiply the cost of every one of thousands of forge invocations.
DEFAULT_FUZZ_RUNS = 32
FORGE_TIMEOUT_SECONDS = 180
TEST_FILENAME = "Generated.t.sol"


@dataclass(frozen=True)
class ForgeResult:
    outcome: str
    tests_run: int
    detail: str


def resolve_closure(repo_root: Path, entry: Path) -> set[Path]:
    """Project-local files `entry` transitively needs.

    Two import styles appear in real projects and both must be followed:
    root-relative (`src/core/Base.sol`) and dot-relative (`./Math.sol`).
    Following only the latter reports a closure of one for every file in a
    codebase that prefers the former, and every build then fails on a missing
    import. External imports (`@openzeppelin/...`, `forge-std/...`) are left
    alone; remappings resolve them without copying a dependency tree per task.
    """
    found: set[Path] = set()
    pending = [entry.resolve()]

    while pending:
        current = pending.pop()
        if current in found or not current.exists():
            continue
        found.add(current)

        for target in IMPORT_PATTERN.findall(current.read_text()):
            resolved = _resolve_import(repo_root, current, target)
            if resolved is not None and resolved not in found:
                pending.append(resolved)

    return found


def _resolve_import(repo_root: Path, importer: Path, target: str) -> Path | None:
    if target.startswith("."):
        candidate = (importer.parent / target).resolve()
    elif target.startswith(f"{SOURCE_ROOT}/"):
        candidate = (repo_root / target).resolve()
    else:
        return None
    return candidate if candidate.exists() else None


def absolute_remappings(repo_root: Path) -> str:
    """Rewrites `remappings.txt` so it resolves from a temp project directory."""
    path = repo_root / "remappings.txt"
    if not path.exists():
        return ""

    lines = []
    for line in path.read_text().splitlines():
        if "=" not in line:
            continue
        prefix, target = line.split("=", 1)
        resolved = str((repo_root / target).resolve())
        # A remapping is a string prefix substitution, so the trailing slash is
        # load-bearing: without it `forge-std/Test.sol` resolves to
        # `.../srcTest.sol`. Path.resolve() drops it.
        if target.endswith("/") and not resolved.endswith("/"):
            resolved += "/"
        lines.append(f"{prefix}={resolved}")
    return "\n".join(lines) + "\n" if lines else ""


def assemble_project(
    workdir: Path,
    repo_root: Path,
    closure: set[Path],
    test_source: str,
    overrides: dict[Path, str] | None = None,
    solc: str = DEFAULT_SOLC,
    fuzz_runs: int = DEFAULT_FUZZ_RUNS,
) -> None:
    """Writes a minimal Foundry project containing exactly `closure`.

    `overrides` replaces a file's contents by its path in the original repo,
    which is how a mutant is injected without touching the real source tree.
    """
    overrides = overrides or {}
    (workdir / "test").mkdir(parents=True, exist_ok=True)

    for path in closure:
        relative = path.relative_to(repo_root)
        destination = workdir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = overrides.get(path)
        if source is None:
            shutil.copyfile(path, destination)
        else:
            destination.write_text(source)

    (workdir / "foundry.toml").write_text(
        FOUNDRY_CONFIG.format(solc=solc, fuzz_runs=fuzz_runs)
    )
    (workdir / "remappings.txt").write_text(absolute_remappings(repo_root))
    (workdir / "test" / TEST_FILENAME).write_text(test_source)


def run_forge_test(workdir: Path, timeout: int = FORGE_TIMEOUT_SECONDS) -> ForgeResult:
    """Runs the suite and classifies the outcome.

    A build failure is `error`, not `failed`: the suite never ran, so it says
    nothing about whether a mutation was detected.
    """
    try:
        completed = subprocess.run(
            ["forge", "test"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ForgeResult("timeout", 0, f"exceeded {timeout}s")
    except FileNotFoundError:
        return ForgeResult("error", 0, "forge not found on PATH")

    return classify_forge_output(completed.stdout + completed.stderr, completed.returncode)


TOTAL_TESTS = re.compile(r"\((\d+) total tests\)")
SUMMARY_FAILED = re.compile(r"tests? passed, (\d+) failed")


def classify_forge_output(output: str, return_code: int) -> ForgeResult:
    """Reads the overall summary line, not the per-suite one.

    forge reports counts twice, once per suite and once overall. Summing every
    match double-counts every test, which would silently corrupt the
    tests-per-suite statistic that the volume findings rest on.
    """
    if _build_failed(output):
        return ForgeResult("error", 0, output[-2000:])

    total_match = TOTAL_TESTS.search(output)
    total = int(total_match.group(1)) if total_match else 0
    failed_match = SUMMARY_FAILED.search(output)
    failed = int(failed_match.group(1)) if failed_match else 0

    if total == 0:
        return ForgeResult("no_tests", 0, output[-2000:])
    if return_code == 0 and failed == 0:
        return ForgeResult("passed", total, output[-2000:])
    return ForgeResult("failed", total, output[-2000:])


def _build_failed(output: str) -> bool:
    return bool(
        re.search(r"Compiler run failed|^Error(?!s? in)", output, re.M)
        or "Unable to resolve import" in output
    )


CONTRACT_DECLARATION = re.compile(r"^\s*(?:abstract\s+)?(contract|library)\s+(\w+)", re.M)
MIN_MUTATION_SITES = 6


def find_contract_candidates(repo_root: Path, min_sites: int = MIN_MUTATION_SITES) -> list[Path]:
    """Source files declaring a concrete contract or library with enough logic.

    Interfaces are excluded: they have no bodies, so there is nothing to mutate
    and nothing a generated test could catch.
    """
    from ruleprobe.solmutate import generate_solidity_mutants

    found = []
    for path in sorted((repo_root / SOURCE_ROOT).rglob("*.sol")):
        source = path.read_text()
        declarations = CONTRACT_DECLARATION.findall(source)
        if not declarations:
            continue
        if all(kind == "interface" for kind, _ in declarations):
            continue
        if len(generate_solidity_mutants(source, min_sites, 0)) < min_sites:
            continue
        found.append(path)
    return found


def primary_contract_name(source: str) -> str | None:
    matches = CONTRACT_DECLARATION.findall(source)
    return matches[-1][1] if matches else None


@dataclass(frozen=True)
class SolidityTask:
    task_id: str
    contract: str
    entry_file: str
    closure: list[str]
    source: str


def freeze_solidity_tasks(
    repo_root: Path,
    tasks_path: Path,
    mutants_path: Path,
    max_mutants_per_task: int | None = None,
    seed: int | None = None,
    limit: int | None = None,
) -> tuple[int, int]:
    """Freezes tasks and *compilable* mutants.

    Compiling every mutant once here is not optional. A mutant that fails to
    build produces outcome `error`, and under "killed = anything but passed"
    that would count as a kill for every suite in every condition, handing out
    free credit for a mutation nobody detected.
    """
    import json

    from ruleprobe.mutate import DEFAULT_MAX_MUTANTS_PER_TASK, DEFAULT_MUTANT_SEED
    from ruleprobe.solmutate import generate_solidity_mutants

    if max_mutants_per_task is None:
        max_mutants_per_task = DEFAULT_MAX_MUTANTS_PER_TASK
    if seed is None:
        seed = DEFAULT_MUTANT_SEED

    candidates = find_contract_candidates(repo_root)
    if limit:
        candidates = candidates[:limit]

    probe = (
        "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.0;\n"
        'import {Test} from "forge-std/Test.sol";\n'
        "contract Probe is Test { function test_builds() public pure { assertTrue(true); } }\n"
    )

    tasks: list[SolidityTask] = []
    mutant_rows: list[dict] = []
    import tempfile

    for entry in candidates:
        closure = resolve_closure(repo_root, entry)
        source = entry.read_text()
        contract = primary_contract_name(source)
        task_id = str(entry.relative_to(repo_root))

        kept = []
        for mutant in generate_solidity_mutants(source, max_mutants_per_task, seed):
            with tempfile.TemporaryDirectory(prefix="ruleprobe-sol-") as workdir:
                work = Path(workdir)
                assemble_project(work, repo_root, closure, probe, overrides={entry: mutant.source})
                if run_forge_test(work).outcome == "passed":
                    kept.append(mutant)

        if not kept:
            continue

        tasks.append(
            SolidityTask(
                task_id=task_id,
                contract=contract or entry.stem,
                entry_file=task_id,
                closure=sorted(str(p.relative_to(repo_root)) for p in closure),
                source=source,
            )
        )
        mutant_rows += [
            {"task_id": task_id, "operator": m.operator, "source": m.source} for m in kept
        ]

    from dataclasses import asdict

    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    with tasks_path.open("w") as f:
        for task in tasks:
            f.write(json.dumps(asdict(task)) + "\n")
    with mutants_path.open("w") as f:
        for row in mutant_rows:
            f.write(json.dumps(row) + "\n")
    return len(tasks), len(mutant_rows)
