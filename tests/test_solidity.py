import pathlib

import pytest

from ruleprobe.solidity import absolute_remappings, resolve_closure


@pytest.fixture
def repo(tmp_path):
    src = tmp_path / "src"
    (src / "core").mkdir(parents=True)
    (src / "utils").mkdir(parents=True)

    (src / "core" / "Vault.sol").write_text(
        'import { Base } from "src/core/Base.sol";\n'
        'import { Math } from "./Math.sol";\n'
        'import { IERC20 } from "@openzeppelin/contracts/IERC20.sol";\n'
        "contract Vault is Base {}\n"
    )
    (src / "core" / "Base.sol").write_text(
        'import { Util } from "src/utils/Util.sol";\ncontract Base {}\n'
    )
    (src / "core" / "Math.sol").write_text("library Math {}\n")
    (src / "utils" / "Util.sol").write_text("library Util {}\n")
    (src / "utils" / "Unused.sol").write_text("library Unused {}\n")
    return tmp_path


def test_closure_includes_the_entry_file(repo):
    closure = resolve_closure(repo, repo / "src/core/Vault.sol")
    assert repo / "src/core/Vault.sol" in closure


def test_closure_follows_root_relative_src_imports(repo):
    """Octant imports as `src/core/Base.sol`, not `./Base.sol`. Following only
    dot-relative imports silently reports a closure of one and every build fails."""
    closure = resolve_closure(repo, repo / "src/core/Vault.sol")
    assert repo / "src/core/Base.sol" in closure


def test_closure_follows_dot_relative_imports(repo):
    closure = resolve_closure(repo, repo / "src/core/Vault.sol")
    assert repo / "src/core/Math.sol" in closure


def test_closure_is_transitive(repo):
    closure = resolve_closure(repo, repo / "src/core/Vault.sol")
    assert repo / "src/utils/Util.sol" in closure


def test_closure_excludes_unreferenced_files(repo):
    closure = resolve_closure(repo, repo / "src/core/Vault.sol")
    assert repo / "src/utils/Unused.sol" not in closure


def test_external_imports_are_left_to_remappings(repo):
    """@openzeppelin resolves through remappings; copying it would mean
    vendoring a dependency tree into every task project."""
    closure = resolve_closure(repo, repo / "src/core/Vault.sol")
    assert not any("openzeppelin" in str(p) for p in closure)


def test_import_cycles_terminate(repo):
    a = repo / "src/core/A.sol"
    b = repo / "src/core/B.sol"
    a.write_text('import { B } from "src/core/B.sol";\ncontract A {}\n')
    b.write_text('import { A } from "src/core/A.sol";\ncontract B {}\n')
    assert resolve_closure(repo, a) == {a, b}


def test_remappings_are_rewritten_to_absolute_paths(tmp_path):
    """A task project lives in a temp dir, so a relative remapping like
    `dependencies/forge-std/` resolves against the wrong root and fails."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "remappings.txt").write_text(
        "forge-std/=dependencies/forge-std-1.14.0/src/\n"
        "@openzeppelin/contracts/=dependencies/oz/contracts/\n"
    )
    out = absolute_remappings(repo)
    assert f"forge-std/={repo}/dependencies/forge-std-1.14.0/src/" in out
    assert all(pathlib.Path(line.split("=", 1)[1]).is_absolute() for line in out.splitlines())


def test_missing_remappings_file_yields_empty(tmp_path):
    assert absolute_remappings(tmp_path) == ""


from ruleprobe.solidity import classify_forge_output

# Real forge 1.x output. Note it reports counts twice, once per suite and once
# overall; summing both double-counts every test.
MIXED = """Compiling 21 files with Solc 0.8.33
Compiler run successful!

Ran 3 tests for test/Generated.t.sol:WadRayProbe
[PASS] test_a() (gas: 386)
[FAIL: assertion failed: 1 != 999] test_fails() (gas: 3477)
Suite result: FAILED. 2 passed; 1 failed; 0 skipped; finished in 3.57ms

Ran 1 test suite in 281.73ms (3.57ms CPU time): 2 tests passed, 1 failed, 0 skipped (3 total tests)
"""

ALL_PASS = """Ran 4 tests for test/Generated.t.sol:P
Suite result: ok. 4 passed; 0 failed; 0 skipped; finished in 1ms

Ran 1 test suite in 200ms (1ms CPU time): 4 tests passed, 0 failed, 0 skipped (4 total tests)
"""

BUILD_FAIL = """Compiling 3 files with Solc 0.8.33
Error (7576): Undeclared identifier.
  --> test/Generated.t.sol:9:20
Compiler run failed
"""

NO_TESTS = """No tests match the provided pattern.
Ran 0 test suites in 1ms (0ms CPU time): 0 tests passed, 0 failed, 0 skipped (0 total tests)
"""


def test_total_is_not_double_counted_across_summary_lines():
    assert classify_forge_output(MIXED, 1).tests_run == 3


def test_a_failing_test_is_classified_failed():
    assert classify_forge_output(MIXED, 1).outcome == "failed"


def test_all_passing_is_classified_passed():
    result = classify_forge_output(ALL_PASS, 0)
    assert result.outcome == "passed"
    assert result.tests_run == 4


def test_build_failure_is_error_not_failed():
    """A suite that never compiled says nothing about whether a mutation was
    detected; scoring it as a kill would credit broken output."""
    assert classify_forge_output(BUILD_FAIL, 1).outcome == "error"


def test_no_tests_is_distinct_from_passing():
    assert classify_forge_output(NO_TESTS, 0).outcome == "no_tests"
